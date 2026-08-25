"""Registers apps.payments TenantOwnedModels with the generic isolation test suite."""

from apps.orders.models import Order
from apps.payments.models import (
    PaymentIdempotencyKey,
    PaymentIntent,
    PaymentTransaction,
    StoreProviderConfig,
    WebhookEvent,
)
from apps.tenancy.testing import register


def _make_order(store, suffix: str) -> Order:
    return Order.objects.create(
        store=store,
        number=f"ORD-{suffix}",
        email=f"{suffix}@example.com",
        currency="SAR",
        subtotal_amount=1000,
        discount_amount=0,
        tax_amount=0,
        shipping_amount=0,
        total_amount=1000,
        shipping_address={"country_code": "SA", "city": "Riyadh", "line1": "1 Test St"},
        shipping_method_name_snapshot="Standard",
    )


def _make_config(store, suffix: str) -> StoreProviderConfig:
    return StoreProviderConfig.objects.create(store=store, provider_key=f"mock-{suffix}")


def _make_intent(store, suffix: str) -> PaymentIntent:
    return PaymentIntent.objects.create(
        store=store,
        order=_make_order(store, suffix),
        provider_config=_make_config(store, suffix),
        amount=1000,
        currency="SAR",
        idempotency_key=f"idem-{suffix}",
    )


@register(StoreProviderConfig)
def _config_factory(store, suffix: str) -> StoreProviderConfig:
    return _make_config(store, suffix)


@register(PaymentIntent)
def _intent_factory(store, suffix: str) -> PaymentIntent:
    return _make_intent(store, suffix)


@register(PaymentTransaction)
def _transaction_factory(store, suffix: str) -> PaymentTransaction:
    intent = _make_intent(store, suffix)
    return PaymentTransaction.objects.create(
        store=store,
        intent=intent,
        kind=PaymentTransaction.Kind.CAPTURE,
        outcome=PaymentTransaction.Outcome.SUCCEEDED,
        amount=1000,
    )


@register(WebhookEvent)
def _webhook_event_factory(store, suffix: str) -> WebhookEvent:
    return WebhookEvent.objects.create(
        store=store,
        provider_config=_make_config(store, suffix),
        external_id=f"evt-{suffix}",
        signature_valid=True,
    )


@register(PaymentIdempotencyKey)
def _payment_idempotency_key_factory(store, suffix: str) -> PaymentIdempotencyKey:
    return PaymentIdempotencyKey.objects.create(
        store=store, key=f"key-{suffix}", request_fingerprint=f"fp-{suffix}"
    )
