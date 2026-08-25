"""
HTTP-level cross-store isolation for the inventory dashboard endpoints,
on top of the generic RLS-level proof in
backend/tests/test_tenant_isolation.py (all 4 inventory tables, via
apps/inventory/tests/isolation_factories.py).
"""

from __future__ import annotations

import pytest

from apps.inventory.tests.conftest import make_client_for
from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_stores_with_stock():
    client_a, owner_a = make_client_for("inv-iso-owner-a@example.com")
    store_a = store_services.create_store(owner=owner_a, name="Inv Store A", slug="inv-iso-a")
    product_a = client_a.post(
        f"/api/v1/dashboard/stores/{store_a.id}/products",
        {"name": "Product A", "slug": "product-a", "sku": "SKU-A", "price_amount": 1000},
        format="json",
    ).data
    location_a = client_a.post(
        f"/api/v1/dashboard/stores/{store_a.id}/inventory/locations",
        {"name": "Warehouse A"},
        format="json",
    ).data
    client_a.post(
        f"/api/v1/dashboard/stores/{store_a.id}/inventory/adjust",
        {
            "variant": product_a["variants"][0]["id"],
            "location": location_a["id"],
            "delta": 50,
            "reason": "seed",
        },
        format="json",
    )

    client_b, owner_b = make_client_for("inv-iso-owner-b@example.com")
    store_b = store_services.create_store(owner=owner_b, name="Inv Store B", slug="inv-iso-b")

    return {
        "client_a": client_a,
        "store_a": store_a,
        "variant_a_id": product_a["variants"][0]["id"],
        "location_a_id": location_a["id"],
        "client_b": client_b,
        "store_b": store_b,
    }


def test_store_a_cannot_list_store_bs_locations(two_stores_with_stock):
    ctx = two_stores_with_stock
    response = ctx["client_a"].get(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/inventory/locations"
    )
    assert response.status_code == 403


def test_store_b_cannot_read_store_as_balances(two_stores_with_stock):
    ctx = two_stores_with_stock
    response = ctx["client_b"].get(
        f"/api/v1/dashboard/stores/{ctx['store_a'].id}/inventory/balances"
    )
    assert response.status_code == 403


def test_store_b_cannot_adjust_store_as_stock(two_stores_with_stock):
    ctx = two_stores_with_stock
    response = ctx["client_b"].post(
        f"/api/v1/dashboard/stores/{ctx['store_a'].id}/inventory/adjust",
        {
            "variant": ctx["variant_a_id"],
            "location": ctx["location_a_id"],
            "delta": 1000,
            "reason": "hijack attempt",
        },
        format="json",
    )
    assert response.status_code == 403

    # Confirm the balance is genuinely untouched, from store A's own view.
    balances = (
        ctx["client_a"].get(f"/api/v1/dashboard/stores/{ctx['store_a'].id}/inventory/balances").data
    )
    assert balances[0]["quantity_on_hand"] == 50


def test_store_b_cannot_read_store_as_movements(two_stores_with_stock):
    ctx = two_stores_with_stock
    response = ctx["client_b"].get(
        f"/api/v1/dashboard/stores/{ctx['store_a'].id}/inventory/movements"
    )
    assert response.status_code == 403
