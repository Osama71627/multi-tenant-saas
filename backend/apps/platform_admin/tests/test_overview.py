"""Approval section 10: no fake metrics -- every number on the overview
must be derived from real backend data."""

from __future__ import annotations

import pytest

from apps.platform_admin import services
from apps.platform_admin.tests.mfa_test_helpers import create_and_authenticate_platform_staff

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def test_overview_counts_match_real_data(make_store, make_subscription):
    before = services.overview_metrics()

    store_a = make_store("Overview A", "platform-overview-a", status="active")
    store_b = make_store("Overview B", "platform-overview-b", status="suspended")
    make_subscription(store_a, status="active")
    make_subscription(store_b, status="canceled")

    after = services.overview_metrics()

    assert after["stores_total"] == before["stores_total"] + 2
    assert (
        after["stores_by_status"].get("active", 0)
        >= before["stores_by_status"].get("active", 0) + 1
    )
    assert (
        after["stores_by_status"].get("suspended", 0)
        >= before["stores_by_status"].get("suspended", 0) + 1
    )
    assert after["subscriptions_by_status"].get("active", 0) >= 1
    assert after["subscriptions_by_status"].get("canceled", 0) >= 1
    assert isinstance(after["plans_total"], int)


def test_overview_orders_and_revenue_match_real_orders(make_store, make_order):
    """Phase 15: orders_total/revenue_by_currency on the platform
    overview must match real Order rows, and only CONFIRMED orders
    count as revenue."""
    before = services.overview_metrics()

    store = make_store("Orders Overview", "platform-orders-overview")
    make_order(store, number="P-1", status="confirmed", total_amount=1500)
    make_order(store, number="P-2", status="confirmed", total_amount=2500)
    make_order(store, number="P-3", status="pending_payment", total_amount=9999)

    after = services.overview_metrics()

    assert after["orders_total"] == before["orders_total"] + 3
    before_revenue = before["revenue_by_currency"].get("SAR", 0)
    assert after["revenue_by_currency"]["SAR"] == before_revenue + 4000


def test_overview_via_http():
    client = create_and_authenticate_platform_staff("overview-http@example.com")

    response = client.get("/api/v1/platform/overview")
    assert response.status_code == 200
    assert "stores_total" in response.data
    assert "subscriptions_by_status" in response.data
    assert "orders_total" in response.data
    assert "revenue_by_currency" in response.data
    assert "orders_last_30_days" in response.data
