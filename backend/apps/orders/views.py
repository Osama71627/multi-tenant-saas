"""
Storefront checkout (`start -> address -> shipping -> complete`) +
dashboard order retrieval (read-only in Phase 8 -- no fulfill/cancel
actions yet, see apps/orders/models.py's module docstring).

`checkout/payment` (docs/ARCHITECTURE.md section 5.3's sample endpoint
list) is deliberately NOT built here: no `PaymentProvider` exists yet
(Phase 9), and approved Phase 8 decision 12 forbids any COD/payment
semantics in this phase. `complete` goes straight from `shipping` to
creating the Order in `pending_payment` -- adding a `checkout/payment`
step later, once Phase 9 lands, does not require touching
`start`/`address`/`shipping`/`complete`.
"""

from __future__ import annotations

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.carts.views import CartAPIView
from apps.orders import services
from apps.orders.models import Order
from apps.orders.serializers import (
    CheckoutAddressRequestSerializer,
    CheckoutSessionSerializer,
    CheckoutShippingRequestSerializer,
    OrderListSerializer,
    OrderSerializer,
)
from apps.stores.mixins import StoreScopedAPIView
from apps.subscriptions.entitlements import QuotaExceededError, StoreNotPurchasableError

_PAYMENT_REQUIRED_ERRORS = (QuotaExceededError, StoreNotPurchasableError)
_BAD_REQUEST_ERRORS = (
    services.IdempotencyKeyRequiredError,
    services.CheckoutStepIncompleteError,
    services.EmptyCartError,
)
_NOT_FOUND_ERRORS = (services.NoActiveCheckoutSessionError,)
_CONFLICT_ERRORS = (
    services.CheckoutSessionExpiredError,
    services.IdempotencyConflictError,
    services.CartRevalidationError,
    services.CouponRevalidationError,
    services.ShippingMethodNotAvailableError,
    services.CheckoutInventoryError,
)


class CheckoutStartView(CartAPIView):
    @extend_schema(responses={201: CheckoutSessionSerializer})
    def post(self, request: Request) -> Response:
        try:
            session = services.start_checkout(cart=self.cart)
        except services.EmptyCartError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CheckoutSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class CheckoutAddressView(CartAPIView):
    @extend_schema(
        request=CheckoutAddressRequestSerializer, responses={200: CheckoutSessionSerializer}
    )
    def post(self, request: Request) -> Response:
        try:
            session = services.get_active_checkout_session(cart=self.cart)
        except _NOT_FOUND_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except _CONFLICT_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        serializer = CheckoutAddressRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = services.set_checkout_address(
            session=session,
            email=serializer.validated_data["email"],
            shipping_address=dict(serializer.validated_data["shipping_address"]),
        )
        return Response(CheckoutSessionSerializer(session).data)


class CheckoutShippingView(CartAPIView):
    @extend_schema(
        request=CheckoutShippingRequestSerializer, responses={200: CheckoutSessionSerializer}
    )
    def post(self, request: Request) -> Response:
        try:
            session = services.get_active_checkout_session(cart=self.cart)
        except _NOT_FOUND_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except _CONFLICT_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        serializer = CheckoutShippingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = services.set_checkout_shipping(
                session=session,
                shipping_method_id=serializer.validated_data["shipping_method_id"],
            )
        except _BAD_REQUEST_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except _CONFLICT_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(CheckoutSessionSerializer(session).data)


class CheckoutCompleteView(CartAPIView):
    @extend_schema(responses={201: OrderSerializer})
    def post(self, request: Request) -> Response:
        idempotency_key = request.headers.get("Idempotency-Key", "")
        try:
            result = services.checkout_complete(
                cart=self.cart,
                store=self.store,
                idempotency_key=idempotency_key,
                order_serializer_cls=OrderSerializer,
            )
        except _BAD_REQUEST_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except _NOT_FOUND_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except _CONFLICT_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except _PAYMENT_REQUIRED_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        return Response(result.response_body, status=result.response_status)


class OrderListView(StoreScopedAPIView):
    @extend_schema(responses=OrderListSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        orders = Order.objects.order_by("-created_at")
        return Response(OrderListSerializer(orders, many=True).data)


class OrderDetailView(StoreScopedAPIView):
    @extend_schema(responses=OrderSerializer)
    def get(self, request: Request, store_id, order_id) -> Response:
        try:
            order = Order.objects.prefetch_related("items").get(id=order_id)
        except (Order.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc
        return Response(OrderSerializer(order).data)
