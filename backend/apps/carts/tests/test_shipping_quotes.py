"""Storefront `/storefront/cart/shipping-quotes` -- consumes apps.shipping.services,
never persists a selection onto the cart (Phase 6/7 scope decision, see
apps/shipping/models.py's module docstring and apps/carts/views.py:CartShippingQuotesView)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _setup_flat_shipping(ctx):
    store_id = ctx["store"].id
    zone = (
        ctx["dashboard_client"]
        .post(
            f"/api/v1/dashboard/stores/{store_id}/shipping/zones",
            {"name": "KSA", "countries": ["SA"]},
            format="json",
        )
        .data
    )
    method = (
        ctx["dashboard_client"]
        .post(
            f"/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone['id']}/methods",
            {"zone": zone["id"], "name": "Standard", "kind": "flat"},
            format="json",
        )
        .data
    )
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{store_id}/shipping/methods/{method['id']}/rates",
        {"method": method["id"], "price_amount": 1500, "currency": "SAR"},
        format="json",
    )
    return zone, method


def test_shipping_quotes_for_empty_cart(store_with_hostname, storefront_client):
    _setup_flat_shipping(store_with_hostname)
    response = storefront_client.get(
        "/api/v1/storefront/cart/shipping-quotes", {"country_code": "SA"}
    )
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["method_name"] == "Standard"
    assert response.data[0]["price_amount"] == 1500


def test_shipping_quotes_with_items_in_cart(variant_in_store, storefront_client):
    _setup_flat_shipping(variant_in_store)
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": variant_in_store["variant_id"], "quantity": 2},
        content_type="application/json",
    )
    response = storefront_client.get(
        "/api/v1/storefront/cart/shipping-quotes", {"country_code": "SA"}
    )
    assert response.status_code == 200
    assert response.data[0]["price_amount"] == 1500


def test_shipping_quotes_no_matching_zone_is_empty_list(store_with_hostname, storefront_client):
    response = storefront_client.get(
        "/api/v1/storefront/cart/shipping-quotes", {"country_code": "EG"}
    )
    assert response.status_code == 200
    assert response.data == []


def test_shipping_quotes_requires_country_code(store_with_hostname, storefront_client):
    response = storefront_client.get("/api/v1/storefront/cart/shipping-quotes")
    assert response.status_code == 400


def test_shipping_quotes_does_not_persist_anything_on_the_cart(
    store_with_hostname, storefront_client
):
    _setup_flat_shipping(store_with_hostname)
    storefront_client.get("/api/v1/storefront/cart/shipping-quotes", {"country_code": "SA"})
    cart = storefront_client.get("/api/v1/storefront/cart")
    assert "shipping_method" not in cart.data
    assert "shipping" not in cart.data
