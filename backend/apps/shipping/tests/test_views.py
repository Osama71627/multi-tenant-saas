from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _create_zone(client, store_id, **overrides):
    payload = {"name": "KSA", "countries": ["SA"]}
    payload.update(overrides)
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/shipping/zones", payload, format="json"
    )


def _create_method(client, store_id, zone_id, **overrides):
    payload = {"zone": str(zone_id), "name": "Flat", "kind": "flat"}
    payload.update(overrides)
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone_id}/methods",
        payload,
        format="json",
    )


def _create_rate(client, store_id, method_id, **overrides):
    payload = {"method": str(method_id), "price_amount": 1500, "currency": "SAR"}
    payload.update(overrides)
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/shipping/methods/{method_id}/rates",
        payload,
        format="json",
    )


def test_create_and_list_zones(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_zone(client, store.id)
    assert response.status_code == 201, response.data
    assert response.data["name"] == "KSA"

    listed = client.get(f"/api/v1/dashboard/stores/{store.id}/shipping/zones")
    assert listed.status_code == 200
    assert len(listed.data) == 1


def test_create_method_under_a_zone(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    zone = _create_zone(client, store.id).data
    response = _create_method(client, store.id, zone["id"])
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "flat"

    listed = client.get(f"/api/v1/dashboard/stores/{store.id}/shipping/zones/{zone['id']}/methods")
    assert listed.status_code == 200
    assert len(listed.data) == 1


def test_method_under_unknown_zone_is_404(owner_client_and_store):
    import uuid

    client, _owner, store = owner_client_and_store
    response = _create_method(client, store.id, uuid.uuid4())
    assert response.status_code == 404


def test_create_rate_under_a_method(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    zone = _create_zone(client, store.id).data
    method = _create_method(client, store.id, zone["id"]).data
    response = _create_rate(client, store.id, method["id"])
    assert response.status_code == 201, response.data
    assert response.data["price_amount"] == 1500


def test_rate_under_unknown_method_is_404(owner_client_and_store):
    import uuid

    client, _owner, store = owner_client_and_store
    response = _create_rate(client, store.id, uuid.uuid4())
    assert response.status_code == 404


def test_list_rates_under_a_method(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    zone = _create_zone(client, store.id).data
    method = _create_method(client, store.id, zone["id"]).data
    _create_rate(client, store.id, method["id"])

    listed = client.get(
        f"/api/v1/dashboard/stores/{store.id}/shipping/methods/{method['id']}/rates"
    )
    assert listed.status_code == 200
    assert len(listed.data) == 1


def test_rate_with_max_below_min_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    zone = _create_zone(client, store.id).data
    method = _create_method(client, store.id, zone["id"]).data
    response = _create_rate(client, store.id, method["id"], min_value=1000, max_value=500)
    assert response.status_code == 400
    assert "max_value" in response.data["detail"]


def test_non_member_cannot_manage_shipping(owner_client_and_store):
    from apps.shipping.tests.conftest import make_client_for

    client, _owner, store = owner_client_and_store
    zone = _create_zone(client, store.id).data

    outsider_client, _outsider = make_client_for("shipping-outsider@example.com")
    assert _create_zone(outsider_client, store.id).status_code == 403
    assert _create_method(outsider_client, store.id, zone["id"]).status_code == 403
