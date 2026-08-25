from __future__ import annotations

import pytest

from apps.platform_admin import services
from apps.platform_admin.tests.mfa_test_helpers import (
    create_and_authenticate_platform_staff as _staff_client,
)

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def test_list_subscriptions_across_stores(make_store, make_subscription):
    store_a = make_store("Sub A", "platform-sub-a")
    store_b = make_store("Sub B", "platform-sub-b")
    sub_a = make_subscription(store_a)
    sub_b = make_subscription(store_b)

    subscriptions = {str(s.id) for s in services.list_subscriptions()}
    assert sub_a in subscriptions
    assert sub_b in subscriptions


def test_list_subscriptions_filtered_by_store(make_store, make_subscription):
    store_a = make_store("Filter A", "platform-filter-a")
    store_b = make_store("Filter B", "platform-filter-b")
    make_subscription(store_a)
    make_subscription(store_b)

    filtered = list(services.list_subscriptions(store_id=store_a))
    assert len(filtered) == 1
    assert str(filtered[0].store_id) == store_a


def test_activate_subscription_reuses_subscriptions_fsm(
    make_store, make_subscription, make_platform_staff_user
):
    store_id = make_store("Activate Sub", "platform-activate-sub")
    sub_id = make_subscription(store_id, status="past_due")
    actor = make_platform_staff_user("subs1@example.com")

    subscription = services.get_subscription(sub_id)
    updated = services.activate_subscription(actor=actor, subscription=subscription)
    assert updated.status == "active"
    assert updated.past_due_since is None


def test_cancel_subscription(make_store, make_subscription, make_platform_staff_user):
    store_id = make_store("Cancel Sub", "platform-cancel-sub")
    sub_id = make_subscription(store_id)
    actor = make_platform_staff_user("subs2@example.com")

    subscription = services.get_subscription(sub_id)
    updated = services.cancel_subscription(actor=actor, subscription=subscription)
    assert updated.status == "canceled"


def test_subscription_lifecycle_via_http(make_store, make_subscription):
    store_id = make_store("HTTP Sub", "platform-http-sub")
    sub_id = make_subscription(store_id)
    client = _staff_client("subs-http@example.com")

    list_response = client.get("/api/v1/platform/subscriptions", {"store_id": store_id})
    assert list_response.status_code == 200
    assert any(row["id"] == sub_id for row in list_response.data)

    activate_response = client.post(f"/api/v1/platform/subscriptions/{sub_id}/activate")
    assert activate_response.status_code == 200
    assert activate_response.data["status"] == "active"

    cancel_response = client.post(f"/api/v1/platform/subscriptions/{sub_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.data["status"] == "canceled"
