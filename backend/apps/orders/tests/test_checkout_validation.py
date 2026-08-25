"""
Authoritative server-side revalidation at `checkout/complete` (approved
Phase 8 decisions 4/9): never trusts `CartItem` price snapshots,
`/cart/reprice`, `/cart/shipping-quotes`, prior coupon state, or prior
inventory checks -- everything is re-derived from scratch at commit
time. Each test here breaks exactly one of those trust points between
`checkout/shipping` and `checkout/complete` and proves `complete`
catches it.
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


def test_shipping_method_disabled_after_selection_is_rejected_at_complete(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    # Merchant disables the method between `shipping` and `complete` --
    # there is no dashboard PATCH endpoint yet (Phase 7 scope), so flip
    # it directly via the DB, tenant-scoped like every other test helper.
    from apps.orders.tests.conftest import store_db_context
    from apps.shipping.models import ShippingMethod

    with store_db_context(ctx["store"]):
        ShippingMethod.objects.filter(id=method["id"]).update(is_active=False)

    response = _complete(storefront_client, "key-disabled-method")
    assert response.status_code == 409


def test_product_archived_after_being_added_to_cart_is_rejected_at_complete(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    ctx["dashboard_client"].patch(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products/{ctx['product_id']}",
        {"status": "archived"},
        format="json",
    )

    response = _complete(storefront_client, "key-archived-product")
    assert response.status_code == 409


def test_price_change_between_shipping_and_complete_uses_the_new_price(
    variant_in_store, storefront_client
):
    """Not an error -- a price change is legitimately picked up, never silently
    ignored in favor of a stale `CartItem` snapshot (approved decision 9)."""
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    from apps.catalog.models import ProductVariant
    from apps.orders.tests.conftest import store_db_context

    with store_db_context(ctx["store"]):
        ProductVariant.objects.filter(id=ctx["variant_id"]).update(price_amount=9999)

    response = _complete(storefront_client, "key-price-change")
    assert response.status_code == 201, response.data
    assert response.data["subtotal_amount"] == 9999
    assert response.data["items"][0]["unit_price_amount"] == 9999


def test_insufficient_stock_at_complete_is_rejected(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"], quantity=1)
    method = setup_flat_shipping(ctx)

    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 5},
        content_type="application/json",
    )
    storefront_client.post("/api/v1/storefront/checkout/start")
    complete_address_and_shipping(storefront_client, method["id"])

    response = _complete(storefront_client, "key-insufficient-stock")
    assert response.status_code == 409
    assert "stock" in response.data["detail"].lower()


def test_coupon_no_longer_valid_at_complete_is_rejected(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)

    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "GONE10", "kind": "percentage", "percentage_value": 10},
        format="json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "GONE10"}, content_type="application/json"
    )
    storefront_client.post("/api/v1/storefront/checkout/start")
    complete_address_and_shipping(storefront_client, method["id"])

    from apps.orders.tests.conftest import store_db_context
    from apps.pricing.models import Coupon

    with store_db_context(ctx["store"]):
        Coupon.objects.filter(code="GONE10").update(is_active=False)

    response = _complete(storefront_client, "key-coupon-invalid")
    assert response.status_code == 409


def test_shipping_step_rejects_a_method_id_not_in_the_current_quotes(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {
            "email": "shopper@example.com",
            "shipping_address": {
                "recipient_name": "T",
                "phone": "+9665",
                "country_code": "SA",
                "city": "Riyadh",
                "line1": "1 St",
            },
        },
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": "01a028ed-0000-7000-8000-000000000000"},
        content_type="application/json",
    )
    assert response.status_code == 409
