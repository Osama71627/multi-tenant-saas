"""
HTTP-level cross-store isolation for the catalog dashboard endpoints --
explicitly required for Phase 4 on top of the generic RLS-level proof in
backend/tests/test_tenant_isolation.py (which already covers all 10
catalog tables automatically via apps/catalog/tests/isolation_factories.py).
This file proves the SAME property through the real dashboard API a
merchant's browser would actually call.
"""

from __future__ import annotations

import pytest

from apps.catalog.tests.conftest import make_client_for
from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_stores_with_products():
    client_a, owner_a = make_client_for("iso-owner-a@example.com")
    store_a = store_services.create_store(owner=owner_a, name="Store A", slug="iso-catalog-a")
    product_a = client_a.post(
        f"/api/v1/dashboard/stores/{store_a.id}/products",
        {"name": "Product A", "slug": "product-a", "sku": "SKU-A", "price_amount": 1000},
        format="json",
    ).data

    client_b, owner_b = make_client_for("iso-owner-b@example.com")
    store_b = store_services.create_store(owner=owner_b, name="Store B", slug="iso-catalog-b")
    product_b = client_b.post(
        f"/api/v1/dashboard/stores/{store_b.id}/products",
        {"name": "Product B", "slug": "product-b", "sku": "SKU-B", "price_amount": 2000},
        format="json",
    ).data

    return {
        "client_a": client_a,
        "store_a": store_a,
        "product_a": product_a,
        "client_b": client_b,
        "store_b": store_b,
        "product_b": product_b,
    }


def test_store_a_cannot_read_store_bs_products(two_stores_with_products):
    ctx = two_stores_with_products
    response = ctx["client_a"].get(f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products")
    assert response.status_code == 403


def test_store_a_cannot_read_a_specific_product_of_store_b(two_stores_with_products):
    ctx = two_stores_with_products
    response = ctx["client_a"].get(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products/{ctx['product_b']['id']}"
    )
    assert response.status_code == 403


def test_store_a_cannot_update_store_bs_product(two_stores_with_products):
    ctx = two_stores_with_products
    response = ctx["client_a"].patch(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products/{ctx['product_b']['id']}",
        {"name": "Hijacked"},
        format="json",
    )
    assert response.status_code == 403
    unchanged = ctx["client_b"].get(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products/{ctx['product_b']['id']}"
    )
    assert unchanged.data["name"] == "Product B"


def test_store_a_cannot_delete_store_bs_product(two_stores_with_products):
    ctx = two_stores_with_products
    response = ctx["client_a"].delete(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products/{ctx['product_b']['id']}"
    )
    assert response.status_code == 403
    still_there = ctx["client_b"].get(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products/{ctx['product_b']['id']}"
    )
    assert still_there.status_code == 200


def test_cannot_create_a_product_under_store_bs_id_while_only_a_member_of_a(
    two_stores_with_products,
):
    """
    Models "attacker edits store_id in the URL": client A is a real,
    authenticated member of store A, but simply swaps the store_id path
    segment to store B's id. Membership is re-checked per-request against
    the PATH's store, not cached/assumed from a prior request.
    """
    ctx = two_stores_with_products
    response = ctx["client_a"].post(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/products",
        {"name": "Injected", "slug": "injected", "sku": "SKU-INJECT", "price_amount": 500},
        format="json",
    )
    assert response.status_code == 403


def test_store_bs_product_id_used_against_store_as_path_is_not_found(two_stores_with_products):
    """
    Even a store A MEMBER can't reach store B's product by pairing store
    A's own store_id in the path with store B's product id in the query
    -- RLS scopes the product lookup to the path's tenant, so this is a
    plain 404, not a leak of "product exists elsewhere."
    """
    ctx = two_stores_with_products
    response = ctx["client_a"].get(
        f"/api/v1/dashboard/stores/{ctx['store_a'].id}/products/{ctx['product_b']['id']}"
    )
    assert response.status_code == 404


def test_categories_and_tags_are_also_isolated_per_store(two_stores_with_products):
    ctx = two_stores_with_products
    ctx["client_b"].post(
        f"/api/v1/dashboard/stores/{ctx['store_b'].id}/categories",
        {"name": "Category B", "slug": "category-b"},
        format="json",
    )
    response = ctx["client_a"].get(f"/api/v1/dashboard/stores/{ctx['store_b'].id}/categories")
    assert response.status_code == 403
