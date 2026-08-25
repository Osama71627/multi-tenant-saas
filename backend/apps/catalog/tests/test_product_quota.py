"""
Phase 10 -- "products" quota enforcement across every mutation that
changes the live count, not just `create_product` (approved architecture
decision 6). `owner_client_and_store` goes through the REAL
`apps.stores.services.create_store` (conftest.py), so these stores carry
a real trial Subscription provisioned via the post-creation hook -- no
special-cased test setup for that part.
"""

from __future__ import annotations

import pytest

from apps.catalog.tests.conftest import store_db_context
from apps.subscriptions.tests.conftest import set_subscription_quota

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


def _create_product(client, store_id, **overrides):
    payload = {"name": "Widget", "slug": "widget", "sku": "WIDGET-001", "price_amount": 1000}
    payload.update(overrides)
    return client.post(f"/api/v1/dashboard/stores/{store_id}/products", payload, format="json")


def _patch_status(client, store_id, product_id, status):
    return client.patch(
        f"/api/v1/dashboard/stores/{store_id}/products/{product_id}",
        {"status": status},
        format="json",
    )


def test_create_product_succeeds_under_the_quota(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    set_subscription_quota(store=store, quota_key="products", limit=1)

    response = _create_product(client, store.id)
    assert response.status_code == 201, response.data


def test_create_product_blocked_at_the_quota_limit(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    set_subscription_quota(store=store, quota_key="products", limit=1)

    first = _create_product(client, store.id, slug="widget-1", sku="WIDGET-1")
    assert first.status_code == 201, first.data

    second = _create_product(client, store.id, slug="widget-2", sku="WIDGET-2")
    assert second.status_code == 402, second.data


def test_archiving_a_product_is_always_allowed_even_at_the_limit(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    set_subscription_quota(store=store, quota_key="products", limit=1)

    created = _create_product(client, store.id)
    product_id = created.data["id"]

    response = _patch_status(client, store.id, product_id, "archived")
    assert response.status_code == 200, response.data
    assert response.data["status"] == "archived"


def test_draft_to_active_transition_is_never_blocked_by_quota(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    set_subscription_quota(store=store, quota_key="products", limit=1)

    created = _create_product(client, store.id)
    product_id = created.data["id"]

    response = _patch_status(client, store.id, product_id, "active")
    assert response.status_code == 200, response.data
    assert response.data["status"] == "active"


def test_unarchiving_a_product_is_blocked_once_it_would_exceed_the_limit(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    set_subscription_quota(store=store, quota_key="products", limit=1)

    a = _create_product(client, store.id, slug="widget-a", sku="WIDGET-A").data["id"]
    archive_response = _patch_status(client, store.id, a, "archived")
    assert archive_response.status_code == 200, archive_response.data

    b = _create_product(client, store.id, slug="widget-b", sku="WIDGET-B")
    assert b.status_code == 201, b.data  # count is back to 1 (only B is non-archived)

    unarchive_a = _patch_status(client, store.id, a, "draft")
    assert unarchive_a.status_code == 402, unarchive_a.data  # would bring count to 2


def test_archived_products_are_excluded_from_the_live_count(owner_client_and_store):
    from apps.subscriptions import entitlements

    client, _owner, store = owner_client_and_store
    set_subscription_quota(store=store, quota_key="products", limit=1)

    a = _create_product(client, store.id, slug="widget-a", sku="WIDGET-A").data["id"]
    _patch_status(client, store.id, a, "archived")

    with store_db_context(store):
        # White-box check that apps.catalog.apps.CatalogConfig.ready() registered
        # the correct, RLS/tenant-scoped counting logic.
        counter = entitlements._live_counters["products"]  # noqa: SLF001
        assert counter(store) == 0
