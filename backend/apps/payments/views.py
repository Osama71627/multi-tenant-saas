"""
Storefront payment initiation, provider webhooks, dashboard COD capture,
dashboard provider-config CRUD (write-only secrets, docs/ARCHITECTURE.md
section 8.3).
"""

from __future__ import annotations

from django.db import IntegrityError
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.orders.models import Order
from apps.payments import services
from apps.payments.models import PaymentIntent, StoreProviderConfig
from apps.payments.serializers import (
    PaymentInitiateRequestSerializer,
    PaymentIntentResponseSerializer,
    StorefrontProviderSerializer,
    StoreProviderConfigSerializer,
)
from apps.stores.mixins import StorefrontAPIView, StoreScopedAPIView, WebhookAPIView
from apps.subscriptions.entitlements import StoreNotPurchasableError

_BAD_REQUEST_ERRORS = (
    services.IdempotencyKeyRequiredError,
    services.ProviderNotConfiguredError,
)
_CONFLICT_ERRORS = (
    services.IdempotencyConflictError,
    services.OrderNotPayableError,
    services.DuplicateActivePaymentIntentError,
)


class StorefrontProviderListView(StorefrontAPIView):
    """`GET /api/v1/storefront/payments/providers` -- Phase 13's checkout
    payment-method picker. Only enabled providers, only `provider_key`."""

    @extend_schema(responses=StorefrontProviderSerializer(many=True))
    def get(self, request: Request) -> Response:
        configs = StoreProviderConfig.objects.filter(is_enabled=True)
        return Response(StorefrontProviderSerializer(configs, many=True).data)


class PaymentInitiateView(StorefrontAPIView):
    @extend_schema(
        request=PaymentInitiateRequestSerializer, responses={201: PaymentIntentResponseSerializer}
    )
    def post(self, request: Request) -> Response:
        serializer = PaymentInitiateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = Order.objects.get(id=serializer.validated_data["order_id"])
        except (Order.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc

        idempotency_key = request.headers.get("Idempotency-Key", "")
        try:
            result = services.initiate_payment(
                order=order,
                store=self.store,
                provider_key=serializer.validated_data["provider_key"],
                idempotency_key=idempotency_key,
            )
        except _BAD_REQUEST_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except _CONFLICT_ERRORS as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except StoreNotPurchasableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        return Response(result.response_body, status=result.response_status)


class PaymentWebhookView(WebhookAPIView):
    def post(self, request: Request, provider: str, store_id) -> Response:
        try:
            config = StoreProviderConfig.objects.get(provider_key=provider, is_enabled=True)
        except StoreProviderConfig.DoesNotExist as exc:
            raise Http404 from exc

        try:
            services.process_webhook(
                store=self.store,
                provider_config=config,
                raw_body=request.body,
                headers=dict(request.headers),
            )
        except services.InvalidWebhookError:
            return Response({"detail": "invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class ManualCodCaptureView(StoreScopedAPIView):
    def post(self, request: Request, store_id, payment_intent_id) -> Response:
        try:
            intent = PaymentIntent.objects.select_related("provider_config").get(
                id=payment_intent_id
            )
        except (PaymentIntent.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc

        try:
            intent = services.capture_manual_cod_payment(payment_intent=intent)
        except services.NotManualCodError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": str(intent.id), "state": intent.state})


class StoreProviderConfigListCreateView(StoreScopedAPIView):
    @extend_schema(responses=StoreProviderConfigSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        configs = StoreProviderConfig.objects.all()
        return Response(StoreProviderConfigSerializer(configs, many=True).data)

    @extend_schema(
        request=StoreProviderConfigSerializer, responses={201: StoreProviderConfigSerializer}
    )
    def post(self, request: Request, store_id) -> Response:
        serializer = StoreProviderConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store)
        except IntegrityError:
            return Response(
                {"detail": "A provider configuration for this provider_key already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
