"""End-to-end checkout HTTP flow (start -> address -> shipping -> complete), real
PostgreSQL, real storefront Host-based resolution -- same pattern as
apps/carts/tests/test_cart_basics.py."""

from __future__ import annotations

import pytest

from apps.orders.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
)

pytestmark = pytest.mark.django_db


def test_full_checkout_flow_creates_an_order(variant_in_store, storefront_client):
    add_stock(variant_in_store["store"], variant_in_store["variant_id"])
    method = setup_flat_shipping(variant_in_store, price_amount=1500)
    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="test-key-1",
    )

    assert response.status_code == 201, response.data
    order = response.data
    assert order["status"] == "pending_payment"
    assert order["email"] == "shopper@example.com"
    assert order["subtotal_amount"] == 2000  # 1 x 2000 (variant_in_store's price)
    assert order["shipping_amount"] == 1500
    assert order["total_amount"] == 2000 + 1500  # no tax rate configured, no coupon
    assert len(order["items"]) == 1
    assert order["items"][0]["variant_sku_snapshot"] == "WIDGET-001"
    assert order["items"][0]["quantity"] == 1
    assert order["shipping_address"]["city"] == "Riyadh"
    assert order["number"].startswith("ORD-")


def test_checkout_start_requires_a_non_empty_cart(store_with_hostname, storefront_client):
    response = storefront_client.post("/api/v1/storefront/checkout/start")
    assert response.status_code == 400


def test_checkout_complete_requires_idempotency_key(variant_in_store, storefront_client):
    method = setup_flat_shipping(variant_in_store)
    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete", content_type="application/json"
    )
    assert response.status_code == 400


def test_checkout_complete_requires_address_and_shipping_steps(variant_in_store, storefront_client):
    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="test-key-incomplete",
    )
    assert response.status_code == 400


def test_checkout_reserves_inventory(variant_in_store, storefront_client):
    """After a successful checkout, the reservation exists under the
    `order:<uuid>` reference contract (apps/orders/models.py)."""
    from apps.orders.models import order_reservation_reference
    from apps.orders.tests.conftest import store_db_context

    ctx = variant_in_store
    location = add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="test-key-reserve",
    )
    assert response.status_code == 201, response.data
    order_id = response.data["id"]

    with store_db_context(ctx["store"]):
        reservation = location.reservations.get(reference=order_reservation_reference(order_id))
        assert reservation.quantity == 1
        assert reservation.status == "active"
