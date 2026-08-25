"""Registers apps.orders TenantOwnedModels with the generic isolation test suite."""

from django.utils import timezone

from apps.carts.models import Cart
from apps.core.tokens import generate_raw_token, hash_raw_token
from apps.orders.models import (
    CheckoutSession,
    IdempotencyKey,
    Order,
    OrderItem,
    OrderNumberSequence,
)
from apps.tenancy.testing import register


def _make_cart(store, suffix: str) -> Cart:
    return Cart.objects.create(
        store=store, token_hash=hash_raw_token(f"{generate_raw_token()}-{suffix}"), currency="SAR"
    )


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


@register(CheckoutSession)
def _checkout_session_factory(store, suffix: str) -> CheckoutSession:
    return CheckoutSession.objects.create(
        store=store, cart=_make_cart(store, suffix), expires_at=timezone.now()
    )


@register(OrderNumberSequence)
def _order_number_sequence_factory(store, suffix: str) -> OrderNumberSequence:
    return OrderNumberSequence.objects.create(store=store)


@register(Order)
def _order_factory(store, suffix: str) -> Order:
    return _make_order(store, suffix)


@register(OrderItem)
def _order_item_factory(store, suffix: str) -> OrderItem:
    order = _make_order(store, suffix)
    return OrderItem.objects.create(
        store=store,
        order=order,
        variant_name_snapshot="Widget",
        variant_sku_snapshot=f"SKU-{suffix}",
        unit_price_amount=1000,
        quantity=1,
        currency="SAR",
    )


@register(IdempotencyKey)
def _idempotency_key_factory(store, suffix: str) -> IdempotencyKey:
    return IdempotencyKey.objects.create(
        store=store, key=f"key-{suffix}", request_fingerprint=f"fp-{suffix}"
    )
