"""
Storefront cart endpoints, under `/api/v1/storefront/cart/...`. First
real consumer of `StorefrontAPIView` (apps/stores/mixins.py) -- Host-
header tenant resolution, `AllowAny` (guest-accessible, no
`apps.customers` yet -- Phase 6 decision, docs/PHASE_6_REPORT.md).

Cart identity is an opaque, unguessable, HASHED token in an HttpOnly
cookie -- never a JWT, never derivable from `cart.id`/`store_id`, and
never treated as proof of *who* the shopper is, only *which cart*. See
apps/carts/models.py and apps/carts/services.py:get_or_create_cart.
"""

from __future__ import annotations

from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.carts import services
from apps.carts.models import CartItem
from apps.carts.serializers import (
    AddCartItemSerializer,
    ApplyCouponSerializer,
    CartSerializer,
    UpdateCartItemSerializer,
)
from apps.carts.services import (
    CouponNotFoundError,
    CurrencyMismatchError,
    VariantNotAvailableError,
)
from apps.catalog.models import ProductVariant
from apps.pricing.services import CouponInvalidError
from apps.shipping import services as shipping_services
from apps.shipping.serializers import ShippingQuoteRequestSerializer, ShippingQuoteSerializer
from apps.stores.mixins import StorefrontAPIView

_CART_COOKIE_NAME = "cart_token"
_CART_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


class CartAPIView(StorefrontAPIView):
    """Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new."""

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        existing_token = request.COOKIES.get(_CART_COOKIE_NAME)
        cart, raw_token = services.get_or_create_cart(store=self.store, raw_token=existing_token)
        self.cart = cart
        self._raw_cart_token = raw_token
        self._cart_token_is_new = raw_token != existing_token

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if getattr(self, "_cart_token_is_new", False):
            response.set_cookie(
                _CART_COOKIE_NAME,
                self._raw_cart_token,
                max_age=_CART_COOKIE_MAX_AGE,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite="Lax",
            )
        return response


def _get_variant_or_404(variant_id) -> ProductVariant:
    try:
        return ProductVariant.objects.select_related("product").get(id=variant_id)
    except (ProductVariant.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


def _get_item_or_404(cart, item_id) -> CartItem:
    try:
        return CartItem.objects.get(id=item_id, cart=cart)
    except (CartItem.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class CartDetailView(CartAPIView):
    @extend_schema(responses=CartSerializer)
    def get(self, request: Request) -> Response:
        return Response(CartSerializer(self.cart).data)


class CartItemListCreateView(CartAPIView):
    @extend_schema(request=AddCartItemSerializer, responses={201: CartSerializer})
    def post(self, request: Request) -> Response:
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = _get_variant_or_404(serializer.validated_data["variant"])

        try:
            services.add_item(
                cart=self.cart, variant=variant, quantity=serializer.validated_data["quantity"]
            )
        except (VariantNotAvailableError, CurrencyMismatchError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        self.cart.refresh_from_db()
        return Response(CartSerializer(self.cart).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(CartAPIView):
    @extend_schema(request=UpdateCartItemSerializer, responses={200: CartSerializer})
    def patch(self, request: Request, item_id) -> Response:
        item = _get_item_or_404(self.cart, item_id)
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_item_quantity(
            cart=self.cart, item=item, quantity=serializer.validated_data["quantity"]
        )
        self.cart.refresh_from_db()
        return Response(CartSerializer(self.cart).data)

    def delete(self, request: Request, item_id) -> Response:
        item = _get_item_or_404(self.cart, item_id)
        services.remove_item(cart=self.cart, item=item)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartCouponView(CartAPIView):
    @extend_schema(request=ApplyCouponSerializer, responses={200: CartSerializer})
    def post(self, request: Request) -> Response:
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.apply_coupon(cart=self.cart, code=serializer.validated_data["code"])
        except (CouponNotFoundError, CouponInvalidError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        self.cart.refresh_from_db()
        return Response(CartSerializer(self.cart).data)

    @extend_schema(responses=CartSerializer)
    def delete(self, request: Request) -> Response:
        services.remove_coupon(cart=self.cart)
        self.cart.refresh_from_db()
        return Response(CartSerializer(self.cart).data)


class CartRepriceView(CartAPIView):
    @extend_schema(responses=CartSerializer)
    def post(self, request: Request) -> Response:
        cart = services.reprice_cart(cart=self.cart)
        return Response(CartSerializer(cart).data)


class CartShippingQuotesView(CartAPIView):
    """
    Informational only -- see apps/shipping/models.py's module docstring
    (scope decision 2). Never a checkout prerequisite: nothing here is
    persisted onto the cart, and Phase 8's Order creation path must
    independently re-price shipping at authoritative checkout time
    (see docs/PHASE_6_REPORT.md's mandatory Phase 8 rule).
    """

    @extend_schema(
        parameters=[
            OpenApiParameter("country_code", str, required=True),
            OpenApiParameter("region", str, required=False),
            OpenApiParameter("postal_code", str, required=False),
        ],
        responses=ShippingQuoteSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        serializer = ShippingQuoteRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        items = [
            (item.variant, item.quantity) for item in self.cart.items.select_related("variant")
        ]
        quotes = shipping_services.get_quotes_for_destination(
            store=self.store,
            country_code=serializer.validated_data["country_code"],
            region=serializer.validated_data["region"],
            postal_code=serializer.validated_data["postal_code"],
            items=items,
            subtotal_amount=self.cart.subtotal_amount,
        )
        return Response(ShippingQuoteSerializer(quotes, many=True).data)
