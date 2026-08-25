"""
Exact Order totals semantics (approved Phase 8 decision 2 required this be
specified and tested, not left implicit) -- see apps/orders/models.py's
module docstring, point 3:

    subtotal_amount  = sum(item.unit_price_amount * item.quantity)
    discount_amount  = calculate_discount(subtotal_amount, coupon)          -- never > subtotal
    tax_amount       = calculate_tax(subtotal_amount - discount_amount, tax_rate)
    shipping_amount  = authoritative shipping quote, NOT taxed (decision 11)
    total_amount     = (subtotal_amount - discount_amount) + tax_amount + shipping_amount

Driven through the real HTTP checkout flow (not calculator unit calls in
isolation) so what's actually proven is `apps.orders.services._build_order`'s
composition, not just `apps.pricing.calculator` in isolation (already covered
by apps/pricing/tests/test_calculator.py).
"""

from __future__ import annotations

import pytest

from apps.orders.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
)

pytestmark = pytest.mark.django_db


def _complete(storefront_client, key: str):
    return storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_totals_with_no_coupon_or_tax_no_shipping_tax(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx, price_amount=1500)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    order = _complete(storefront_client, "semantics-1").data
    assert order["subtotal_amount"] == 2000
    assert order["discount_amount"] == 0
    assert order["tax_amount"] == 0
    assert order["shipping_amount"] == 1500
    assert order["total_amount"] == 2000 + 1500


def test_totals_with_tax_excludes_shipping_from_the_taxable_base(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx, price_amount=1500)
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/tax-rates",
        {"name": "VAT", "country_code": "SA", "rate_percent": "15.00"},
        format="json",
    )
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    order = _complete(storefront_client, "semantics-2").data
    # subtotal=2000, tax = 15% of 2000 (NOT 2000+1500) = 300
    assert order["subtotal_amount"] == 2000
    assert order["tax_amount"] == 300
    assert order["shipping_amount"] == 1500
    assert order["total_amount"] == 2000 + 300 + 1500


def test_totals_with_coupon_and_tax_and_shipping_composed_correctly(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx, price_amount=1500)
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/tax-rates",
        {"name": "VAT", "country_code": "SA", "rate_percent": "15.00"},
        format="json",
    )
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "SAVE10", "kind": "percentage", "percentage_value": 10},
        format="json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "SAVE10"}, content_type="application/json"
    )
    storefront_client.post("/api/v1/storefront/checkout/start")
    complete_address_and_shipping(storefront_client, method["id"])

    order = _complete(storefront_client, "semantics-3").data
    # subtotal=2000, discount=10%=200, taxable=1800, tax=15% of 1800=270
    assert order["subtotal_amount"] == 2000
    assert order["discount_amount"] == 200
    assert order["tax_amount"] == 270
    assert order["shipping_amount"] == 1500
    assert order["total_amount"] == (2000 - 200) + 270 + 1500
    assert order["coupon_code_snapshot"] == "SAVE10"


def test_line_total_amount_is_unit_price_times_quantity(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"], quantity=5)
    method = setup_flat_shipping(ctx)
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 3},
        content_type="application/json",
    )
    storefront_client.post("/api/v1/storefront/checkout/start")
    complete_address_and_shipping(storefront_client, method["id"])

    order = _complete(storefront_client, "semantics-4").data
    item = order["items"][0]
    assert item["quantity"] == 3
    assert item["unit_price_amount"] == 2000
    assert item["line_total_amount"] == 6000
    assert order["subtotal_amount"] == 6000
