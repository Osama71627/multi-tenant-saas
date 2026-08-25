"""
Phase 10 -- "orders_per_period" quota enforcement on checkout/complete,
and the required proof that a retried checkout (same Idempotency-Key)
never double-consumes it (approved architecture decision 8).
"""

from __future__ import annotations

import pytest

from apps.orders.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
)
from apps.subscriptions.tests.conftest import set_subscription_quota

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


def _complete(storefront_client, key: str):
    return storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _usage_used(store) -> int:
    from apps.subscriptions.models import UsageRecord

    with store_db_context(store):
        record = UsageRecord.objects.filter(quota_key="orders_per_period").first()
        return record.used if record else 0


def test_checkout_succeeds_under_the_quota(variant_in_store, storefront_client):
    store = variant_in_store["store"]
    set_subscription_quota(store=store, quota_key="orders_per_period", limit=1)
    add_stock(store, variant_in_store["variant_id"])
    method = setup_flat_shipping(variant_in_store)
    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    response = _complete(storefront_client, "quota-ok-1")
    assert response.status_code == 201, response.data
    assert _usage_used(store) == 1


def test_checkout_blocked_once_the_period_quota_is_exhausted(variant_in_store, storefront_client):
    store = variant_in_store["store"]
    set_subscription_quota(store=store, quota_key="orders_per_period", limit=1)
    add_stock(store, variant_in_store["variant_id"], quantity=10)
    method = setup_flat_shipping(variant_in_store)

    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])
    first = _complete(storefront_client, "quota-block-1")
    assert first.status_code == 201, first.data

    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])
    second = _complete(storefront_client, "quota-block-2")
    assert second.status_code == 402, second.data
    assert _usage_used(store) == 1  # the rejected attempt never incremented anything


def test_retried_checkout_with_the_same_idempotency_key_does_not_double_consume_quota(
    variant_in_store, storefront_client
):
    """`_build_order` only ever runs once per successful checkout: a
    retried request with the SAME Idempotency-Key is short-circuited by
    `checkout_complete`'s claim/replay logic before `_build_order` (and
    therefore `entitlements.check_quota`) is reached a second time."""
    store = variant_in_store["store"]
    set_subscription_quota(store=store, quota_key="orders_per_period", limit=1)
    add_stock(store, variant_in_store["variant_id"])
    method = setup_flat_shipping(variant_in_store)
    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    first = _complete(storefront_client, "quota-idem-1")
    assert first.status_code == 201, first.data

    replay = _complete(storefront_client, "quota-idem-1")
    assert replay.status_code == 201, replay.data
    assert replay.data == first.data  # a REPLAY of the same Order, not a second one

    assert _usage_used(store) == 1  # still exactly one increment
