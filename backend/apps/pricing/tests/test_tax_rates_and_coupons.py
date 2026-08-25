from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _create_tax_rate(client, store_id, **overrides):
    payload = {"name": "Saudi VAT", "country_code": "SA", "rate_percent": "15.00"}
    payload.update(overrides)
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/pricing/tax-rates", payload, format="json"
    )


def _create_coupon(client, store_id, **overrides):
    payload = {"code": "SAVE10", "kind": "percentage", "percentage_value": 10}
    payload.update(overrides)
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/pricing/coupons", payload, format="json"
    )


def test_create_tax_rate(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_tax_rate(client, store.id)
    assert response.status_code == 201, response.data
    assert response.data["is_active"] is True


def test_cannot_have_two_active_tax_rates_in_the_same_store(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_tax_rate(client, store.id)
    second = _create_tax_rate(client, store.id, name="Another VAT")
    assert second.status_code == 400


def test_can_have_an_inactive_second_tax_rate(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_tax_rate(client, store.id)
    second = _create_tax_rate(client, store.id, name="Old VAT", is_active=False)
    assert second.status_code == 201


def test_tax_rate_percent_out_of_range_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_tax_rate(client, store.id, rate_percent="150.00")
    assert response.status_code == 400


def test_create_percentage_coupon(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_coupon(client, store.id)
    assert response.status_code == 201, response.data
    assert response.data["code"] == "SAVE10"


def test_coupon_code_is_normalized_to_uppercase(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_coupon(client, store.id, code="save10")
    assert response.data["code"] == "SAVE10"


def test_create_fixed_amount_coupon(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_coupon(
        client,
        store.id,
        code="FLAT20",
        kind="fixed_amount",
        percentage_value=None,
        fixed_amount_value=2000,
        currency="SAR",
    )
    assert response.status_code == 201, response.data


def test_fixed_amount_coupon_without_currency_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_coupon(
        client,
        store.id,
        code="FLAT20",
        kind="fixed_amount",
        percentage_value=None,
        fixed_amount_value=2000,
    )
    assert response.status_code == 400


def test_percentage_coupon_with_a_fixed_amount_value_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = _create_coupon(client, store.id, fixed_amount_value=500)
    assert response.status_code == 400


def test_duplicate_coupon_code_in_same_store_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _create_coupon(client, store.id)
    second = _create_coupon(client, store.id)
    assert second.status_code == 400


def test_non_member_cannot_create_tax_rate_or_coupon(owner_client_and_store):
    from apps.pricing.tests.conftest import make_client_for

    _client, _owner, store = owner_client_and_store
    outsider_client, _outsider = make_client_for("pricing-outsider@example.com")
    assert _create_tax_rate(outsider_client, store.id).status_code == 403
    assert _create_coupon(outsider_client, store.id).status_code == 403
