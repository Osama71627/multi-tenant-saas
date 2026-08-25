"""Dashboard order retrieval (read-only in Phase 8) -- same 404-vs-403 pattern as every
prior StoreScopedAPIView surface (apps/stores/mixins.py). Cross-tenant regression tests
per approved Phase 8 decision 14."""

from __future__ import annotations

import pytest

from apps.orders.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    make_client_for,
    setup_flat_shipping,
)

pytestmark = pytest.mark.django_db


def _create_order(ctx, storefront_client):
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="dashboard-test-key",
    )
    assert response.status_code == 201, response.data
    return response.data


def test_dashboard_can_list_orders(variant_in_store, storefront_client):
    ctx = variant_in_store
    order = _create_order(ctx, storefront_client)

    response = ctx["dashboard_client"].get(f"/api/v1/dashboard/stores/{ctx['store'].id}/orders")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["number"] == order["number"]


def test_dashboard_can_retrieve_order_detail(variant_in_store, storefront_client):
    ctx = variant_in_store
    order = _create_order(ctx, storefront_client)

    response = ctx["dashboard_client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/orders/{order['id']}"
    )
    assert response.status_code == 200
    assert response.data["number"] == order["number"]
    assert len(response.data["items"]) == 1


def test_unknown_order_id_is_404(variant_in_store):
    import uuid

    ctx = variant_in_store
    response = ctx["dashboard_client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/orders/{uuid.uuid4()}"
    )
    assert response.status_code == 404


def test_non_member_cannot_list_or_retrieve_orders(variant_in_store, storefront_client):
    ctx = variant_in_store
    order = _create_order(ctx, storefront_client)

    outsider_client, _outsider = make_client_for("orders-outsider@example.com")
    assert (
        outsider_client.get(f"/api/v1/dashboard/stores/{ctx['store'].id}/orders").status_code == 403
    )
    assert (
        outsider_client.get(
            f"/api/v1/dashboard/stores/{ctx['store'].id}/orders/{order['id']}"
        ).status_code
        == 403
    )


def test_orders_from_another_store_are_invisible_even_by_id(variant_in_store, storefront_client):
    """Cross-tenant regression: Store B's dashboard, hitting Store A's real order id
    directly, must 404 -- RLS makes the row simply not exist for Store B's context,
    not a 403 (same reasoning as every prior StoreScopedAPIView, docs/PHASE_3_REPORT.md)."""
    ctx = variant_in_store
    order = _create_order(ctx, storefront_client)

    from apps.stores import services as store_services

    other_client, other_owner = make_client_for("other-store-owner@example.com")
    other_store = store_services.create_store(owner=other_owner, name="Other Co", slug="other-co")

    response = other_client.get(f"/api/v1/dashboard/stores/{other_store.id}/orders/{order['id']}")
    assert response.status_code == 404
