"""
Phase 15 DoD: "numbers match the source". Every assertion here creates
real Order rows (via the existing checkout/order-creation machinery's
lower-level factories, same pattern as apps/orders/tests) and checks the
aggregation matches them exactly -- plus the standard tenant-isolation
proof (store A's analytics never includes store B's orders), the same
discipline every other tenant-scoped surface in this project already
has.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.analytics import services
from apps.orders.models import Order
from apps.stores import services as store_services
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


def _make_order(
    *, store, number: str, status: str, total_amount: int, currency: str = "SAR"
) -> Order:
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return Order.objects.create(
                store=store,
                number=number,
                email="buyer@example.com",
                status=status,
                currency=currency,
                subtotal_amount=total_amount,
                discount_amount=0,
                tax_amount=0,
                shipping_amount=0,
                total_amount=total_amount,
                shipping_address={},
                shipping_method_name_snapshot="Standard",
            )
        finally:
            clear_tenant_context_from_db()


def _owner_client_and_store(email: str, slug: str):
    user = PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    store = store_services.create_store(owner=user, name=slug, slug=slug)
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login", {"email": email, "password": "correct-h0rse!"}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client, store


def _metrics_in_context(store):
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return services.store_overview_metrics(store=store)
        finally:
            clear_tenant_context_from_db()


def test_orders_total_and_revenue_match_created_orders():
    _client, store = _owner_client_and_store("analytics1@example.com", "analytics-store-1")
    _make_order(store=store, number="A-1", status=Order.Status.CONFIRMED, total_amount=1000)
    _make_order(store=store, number="A-2", status=Order.Status.CONFIRMED, total_amount=2500)
    _make_order(store=store, number="A-3", status=Order.Status.PENDING_PAYMENT, total_amount=500)
    _make_order(store=store, number="A-4", status=Order.Status.CANCELLED, total_amount=999)

    metrics = _metrics_in_context(store)

    assert metrics["orders_total"] == 4
    assert metrics["orders_by_status"] == {"confirmed": 2, "pending_payment": 1, "cancelled": 1}
    # Only CONFIRMED orders count as revenue -- pending/cancelled excluded.
    assert metrics["revenue_by_currency"] == {"SAR": 3500}


def test_cancelled_and_pending_orders_excluded_from_revenue():
    _client, store = _owner_client_and_store("analytics2@example.com", "analytics-store-2")
    _make_order(store=store, number="B-1", status=Order.Status.PENDING_PAYMENT, total_amount=5000)
    _make_order(store=store, number="B-2", status=Order.Status.CANCELLED, total_amount=5000)

    metrics = _metrics_in_context(store)

    assert metrics["orders_total"] == 2
    assert metrics["revenue_by_currency"] == {}


def test_empty_store_has_zeroed_metrics():
    _client, store = _owner_client_and_store("analytics3@example.com", "analytics-store-3")

    metrics = _metrics_in_context(store)

    assert metrics == {
        "orders_total": 0,
        "orders_by_status": {},
        "revenue_by_currency": {},
        "orders_last_30_days": [],
    }


def test_store_a_analytics_never_includes_store_bs_orders():
    client_a, store_a = _owner_client_and_store("analytics4a@example.com", "analytics-store-4a")
    _client_b, store_b = _owner_client_and_store("analytics4b@example.com", "analytics-store-4b")
    _make_order(store=store_a, number="C-1", status=Order.Status.CONFIRMED, total_amount=1111)
    _make_order(store=store_b, number="D-1", status=Order.Status.CONFIRMED, total_amount=9999)

    response = client_a.get(f"/api/v1/dashboard/stores/{store_a.id}/analytics/overview")
    assert response.status_code == 200
    assert response.data["orders_total"] == 1
    assert response.data["revenue_by_currency"] == {"SAR": 1111}


def test_analytics_endpoint_requires_membership():
    _client_a, store_a = _owner_client_and_store("analytics5a@example.com", "analytics-store-5a")
    client_b, _store_b = _owner_client_and_store("analytics5b@example.com", "analytics-store-5b")

    response = client_b.get(f"/api/v1/dashboard/stores/{store_a.id}/analytics/overview")
    assert response.status_code == 403


def test_analytics_endpoint_requires_authentication():
    _client, store = _owner_client_and_store("analytics6@example.com", "analytics-store-6")

    response = APIClient().get(f"/api/v1/dashboard/stores/{store.id}/analytics/overview")
    assert response.status_code == 401
