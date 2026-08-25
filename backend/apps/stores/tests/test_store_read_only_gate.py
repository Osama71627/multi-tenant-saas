"""
Phase 10, approved architecture decision 8/11: a `read_only` Store still
serves ordinary dashboard reads, but every unsafe-method dashboard
request is rejected with 402 -- proven at the real HTTP layer through
`StoreScopedAPIView` (apps/stores/mixins.py), which reaches this via
`apps.stores.hooks.check_write_gates` (registered by
`apps.subscriptions.apps.SubscriptionsConfig.ready()`), never a direct
import of apps.subscriptions.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services
from apps.stores.models import Store

pytestmark = pytest.mark.django_db


def _login_as(email: str, password: str = "correct-h0rse!") -> APIClient:  # noqa: S107
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


@pytest.fixture
def owner_client_and_store():
    email = "readonly-gate-owner@example.com"
    owner = PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    client = _login_as(email)
    store = store_services.create_store(owner=owner, name="Read-Only Co", slug="readonly-co")
    return client, owner, store


def _mark_read_only(store: Store) -> None:
    from apps.tenancy.context import TenantContext, tenant_context
    from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            store.status = Store.Status.READ_ONLY
            store.save(update_fields=["status", "updated_at"])
        finally:
            clear_tenant_context_from_db()


def test_read_only_store_still_serves_dashboard_reads(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _mark_read_only(store)

    response = client.get(f"/api/v1/dashboard/stores/{store.id}")
    assert response.status_code == 200


def test_read_only_store_rejects_a_dashboard_write_with_402(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _mark_read_only(store)

    response = client.post(
        f"/api/v1/dashboard/stores/{store.id}/products",
        {"name": "Widget", "slug": "widget", "sku": "WIDGET-001", "price_amount": 1000},
        format="json",
    )
    assert response.status_code == 402, response.data


def test_active_store_dashboard_writes_are_unaffected(owner_client_and_store):
    client, _owner, store = owner_client_and_store

    response = client.post(
        f"/api/v1/dashboard/stores/{store.id}/products",
        {"name": "Widget", "slug": "widget", "sku": "WIDGET-001", "price_amount": 1000},
        format="json",
    )
    assert response.status_code == 201, response.data
