"""
The Phase 6 DoD: "إعادة تسعير كاملة على الخادم" (full server-side
re-pricing). `POST /storefront/cart/reprice` is the explicit operation
that refreshes stale cart-item price snapshots from the CURRENT catalog
state -- proven here by actually changing a merchant's price mid-cart-
session and confirming the cart does NOT silently reflect it until
reprice is explicitly called.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_cart_keeps_the_snapshotted_price_until_explicitly_repriced(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    add_response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    assert add_response.data["subtotal_amount"] == 2000

    # Merchant changes the price while the item sits in the cart. No
    # variant-update HTTP endpoint exists yet in this project's current
    # API surface (apps.catalog only supports creating new variants), so
    # this simulates the change directly at the row level -- exactly
    # what a future variant-update endpoint would do underneath.
    from apps.carts.tests.conftest import store_db_context
    from apps.catalog.models import ProductVariant

    with store_db_context(ctx["store"]):
        ProductVariant.objects.filter(id=ctx["variant_id"]).update(price_amount=3500)

    # The cart's own read still shows the OLD, snapshotted price --
    # browsing a cart must never silently reprice itself.
    unchanged = storefront_client.get("/api/v1/storefront/cart")
    assert unchanged.data["subtotal_amount"] == 2000

    # Only the explicit reprice operation picks up the new price.
    repriced = storefront_client.post("/api/v1/storefront/cart/reprice")
    assert repriced.status_code == 200
    assert repriced.data["items"][0]["unit_price_amount"] == 3500
    assert repriced.data["subtotal_amount"] == 3500
    assert repriced.data["total_amount"] == 3500


def test_reprice_removes_a_line_whose_product_became_a_draft(variant_in_store, storefront_client):
    ctx = variant_in_store
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )

    # Merchant un-publishes the product after it was added to the cart.
    ctx["dashboard_client"].patch(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products/{ctx['product_id']}",
        {"status": "draft"},
        format="json",
    )

    response = storefront_client.post("/api/v1/storefront/cart/reprice")
    assert response.status_code == 200
    assert response.data["items"] == []
    assert response.data["total_amount"] == 0


def test_reprice_with_tax_recomputes_totals_from_the_new_price(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/tax-rates",
        {"name": "VAT", "country_code": "SA", "rate_percent": "15.00"},
        format="json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )

    from apps.carts.tests.conftest import store_db_context
    from apps.catalog.models import ProductVariant

    with store_db_context(ctx["store"]):
        ProductVariant.objects.filter(id=ctx["variant_id"]).update(price_amount=1000)

    response = storefront_client.post("/api/v1/storefront/cart/reprice")
    assert response.data["subtotal_amount"] == 1000
    assert response.data["tax_amount"] == 150
    assert response.data["total_amount"] == 1150
