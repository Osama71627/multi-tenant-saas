"""
`POST /api/v1/dashboard/stores/<id>/products` -- creates a Product with
exactly one default variant, atomically (Phase 4 architecture rule 1).
Runs against real PostgreSQL 18.6.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Product, ProductVariant
from apps.catalog.tests.conftest import make_client_for, store_db_context
from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


def _create_product(client, store_id, **overrides):
    payload = {
        "name": "Cookbook",
        "slug": "cookbook",
        "sku": "BOOK-001",
        "price_amount": 4500,
    }
    payload.update(overrides)
    return client.post(f"/api/v1/dashboard/stores/{store_id}/products", payload, format="json")


def test_member_can_create_a_product(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_product(client, store.id)
    assert response.status_code == 201, response.data
    assert response.data["name"] == "Cookbook"
    assert response.data["status"] == "draft"
    assert len(response.data["variants"]) == 1


def test_created_product_has_exactly_one_default_variant(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_product(client, store.id)
    variant = response.data["variants"][0]
    assert variant["is_default"] is True
    assert variant["sku"] == "BOOK-001"
    assert variant["price_amount"] == 4500
    assert variant["currency"] == "SAR"  # Store.default_currency


def test_currency_defaults_to_the_stores_currency_but_is_overridable(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_product(
        client, store.id, currency="AED", slug="cookbook-aed", sku="BOOK-AED"
    )
    assert response.data["variants"][0]["currency"] == "AED"


def test_unauthenticated_request_cannot_create_a_product(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    response = _create_product(APIClient(), store.id)
    assert response.status_code == 401


def test_non_member_cannot_create_a_product(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    outsider_client, _outsider = make_client_for("catalog-outsider@example.com")
    response = _create_product(outsider_client, store.id)
    assert response.status_code == 403
    with store_db_context(store):
        assert not Product.objects.filter(slug="cookbook").exists()


def test_duplicate_slug_within_the_same_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_product(client, store.id)
    second = _create_product(client, store.id, sku="BOOK-002")
    assert second.status_code == 400


def test_duplicate_sku_within_the_same_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_product(client, store.id)
    second = _create_product(client, store.id, slug="another-book")
    assert second.status_code == 400


def test_same_slug_is_allowed_in_a_different_store(owner_client_and_store):
    client, owner, _store_a = owner_client_and_store
    store_b = store_services.create_store(
        owner=owner, name="Second Store", slug="second-catalog-store"
    )
    first = _create_product(client, _store_a.id)
    second = _create_product(client, store_b.id)
    assert first.status_code == second.status_code == 201


def test_failed_product_creation_leaves_no_orphaned_variant(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_product(client, store.id)
    with store_db_context(store):
        before = ProductVariant.objects.count()

    response = _create_product(client, store.id, sku="BOOK-002")  # duplicate slug
    assert response.status_code == 400
    with store_db_context(store):
        assert ProductVariant.objects.count() == before


def test_product_status_defaults_to_draft(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_product(client, store.id)
    assert response.data["status"] == "draft"


def test_product_detail_and_list_are_membership_gated(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    created = _create_product(client, store.id)
    product_id = created.data["id"]

    outsider_client, _outsider = make_client_for("catalog-list-outsider@example.com")
    assert outsider_client.get(f"/api/v1/dashboard/stores/{store.id}/products").status_code == 403
    assert (
        outsider_client.get(
            f"/api/v1/dashboard/stores/{store.id}/products/{product_id}"
        ).status_code
        == 403
    )

    assert client.get(f"/api/v1/dashboard/stores/{store.id}/products").status_code == 200
    assert (
        client.get(f"/api/v1/dashboard/stores/{store.id}/products/{product_id}").status_code == 200
    )


def test_member_can_update_their_own_product(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    product_id = _create_product(client, store.id).data["id"]

    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}/products/{product_id}",
        {"name": "Renamed Cookbook", "status": "active"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Renamed Cookbook"
    assert response.data["status"] == "active"


def test_updating_a_product_to_a_slug_already_used_in_the_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_product(client, store.id)  # slug="cookbook"
    other_id = _create_product(client, store.id, slug="second-book", sku="BOOK-002").data["id"]

    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}/products/{other_id}",
        {"slug": "cookbook"},
        format="json",
    )
    assert response.status_code == 400


def test_member_can_delete_their_own_product(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    product_id = _create_product(client, store.id).data["id"]

    response = client.delete(f"/api/v1/dashboard/stores/{store.id}/products/{product_id}")
    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/dashboard/stores/{store.id}/products/{product_id}")
    assert follow_up.status_code == 404


def test_product_list_can_be_filtered_by_status(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    draft_id = _create_product(client, store.id).data["id"]
    active_id = _create_product(client, store.id, slug="second-book", sku="BOOK-002").data["id"]
    client.patch(
        f"/api/v1/dashboard/stores/{store.id}/products/{active_id}",
        {"status": "active"},
        format="json",
    )

    active_only = client.get(f"/api/v1/dashboard/stores/{store.id}/products?status=active")
    assert [p["id"] for p in active_only.data] == [active_id]

    draft_only = client.get(f"/api/v1/dashboard/stores/{store.id}/products?status=draft")
    assert [p["id"] for p in draft_only.data] == [draft_id]
