from __future__ import annotations

import pytest

from apps.inventory.tests.conftest import make_client_for

pytestmark = pytest.mark.django_db


def test_member_can_create_a_location(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.post(
        f"/api/v1/dashboard/stores/{store.id}/inventory/locations",
        {"name": "Main Warehouse"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["name"] == "Main Warehouse"
    assert response.data["is_active"] is True


def test_duplicate_location_name_in_same_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    url = f"/api/v1/dashboard/stores/{store.id}/inventory/locations"
    client.post(url, {"name": "Main Warehouse"}, format="json")
    second = client.post(url, {"name": "Main Warehouse"}, format="json")
    assert second.status_code == 400


def test_same_location_name_allowed_in_a_different_store(owner_client_and_store):
    from apps.stores import services as store_services

    client, owner, store_a = owner_client_and_store
    store_b = store_services.create_store(owner=owner, name="Second Inv Co", slug="second-inv-co")

    r1 = client.post(
        f"/api/v1/dashboard/stores/{store_a.id}/inventory/locations",
        {"name": "Main Warehouse"},
        format="json",
    )
    r2 = client.post(
        f"/api/v1/dashboard/stores/{store_b.id}/inventory/locations",
        {"name": "Main Warehouse"},
        format="json",
    )
    assert r1.status_code == r2.status_code == 201


def test_no_default_location_is_auto_created_for_a_new_store(owner_client_and_store):
    """Phase 5 rule: no implicit/default Location, ever -- must be explicitly created."""
    client, _owner, store = owner_client_and_store
    response = client.get(f"/api/v1/dashboard/stores/{store.id}/inventory/locations")
    assert response.status_code == 200
    assert response.data == []


def test_non_member_cannot_create_a_location(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    outsider_client, _outsider = make_client_for("inventory-outsider@example.com")
    response = outsider_client.post(
        f"/api/v1/dashboard/stores/{store.id}/inventory/locations",
        {"name": "Sneaky Warehouse"},
        format="json",
    )
    assert response.status_code == 403
