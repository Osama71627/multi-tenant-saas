from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _create_category(client, store_id, **overrides):
    payload = {"name": "Electronics", "slug": "electronics"}
    payload.update(overrides)
    return client.post(f"/api/v1/dashboard/stores/{store_id}/categories", payload, format="json")


def _create_tag(client, store_id, **overrides):
    payload = {"name": "Sale", "slug": "sale"}
    payload.update(overrides)
    return client.post(f"/api/v1/dashboard/stores/{store_id}/tags", payload, format="json")


def test_create_category(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_category(client, store.id)
    assert response.status_code == 201, response.data


def test_duplicate_category_slug_in_same_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_category(client, store.id)
    response = _create_category(client, store.id)
    assert response.status_code == 400


def test_category_can_have_a_parent_in_the_same_store(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    parent = _create_category(client, store.id, name="Root", slug="root")
    child = _create_category(client, store.id, name="Child", slug="child", parent=parent.data["id"])
    assert child.status_code == 201
    # PrimaryKeyRelatedField.to_representation returns the raw pk (a
    # uuid.UUID), while the auto-generated "id" field is a plain
    # UUIDField whose to_representation stringifies it -- both correct,
    # just different DRF field types, hence the str() here.
    assert str(child.data["parent"]) == parent.data["id"]


def test_create_tag(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_tag(client, store.id)
    assert response.status_code == 201, response.data


def test_duplicate_tag_slug_in_same_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_tag(client, store.id)
    response = _create_tag(client, store.id)
    assert response.status_code == 400


def test_list_categories(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_category(client, store.id)
    response = client.get(f"/api/v1/dashboard/stores/{store.id}/categories")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["slug"] == "electronics"


def test_list_tags(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_tag(client, store.id)
    response = client.get(f"/api/v1/dashboard/stores/{store.id}/tags")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["slug"] == "sale"
