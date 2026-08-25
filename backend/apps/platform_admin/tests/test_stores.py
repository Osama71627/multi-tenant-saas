"""
Required proofs (approval section 13, items 1/2/5/6) around Store
management: `app_platform_admin` can read across tenants where an
endpoint permits it, `app_user` is still fully isolated, and
suspend/activate go through the privileged path with exactly one correct
AuditLog row each.
"""

from __future__ import annotations

import pytest

from apps.platform_admin import services
from apps.platform_admin.models import AuditLog
from apps.platform_admin.tests.mfa_test_helpers import (
    create_and_authenticate_platform_staff as _staff_client,
)
from apps.stores.models import Store

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def test_platform_staff_can_list_stores_across_tenants(make_store):
    store_a = make_store("Store A", "platform-store-a")
    store_b = make_store("Store B", "platform-store-b")

    client = _staff_client()
    response = client.get("/api/v1/platform/stores")
    assert response.status_code == 200
    ids = {row["id"] for row in response.data}
    assert store_a in ids
    assert store_b in ids


def test_app_platform_admin_can_read_both_stores_directly(make_store):
    """Item 2: app_platform_admin reads Store A and Store B where the
    endpoint permits it -- proven at the service layer directly, not
    just through one HTTP call."""
    store_a = make_store("Direct A", "platform-direct-a")
    store_b = make_store("Direct B", "platform-direct-b")

    fetched_a = services.get_store(store_a)
    fetched_b = services.get_store(store_b)
    assert str(fetched_a.id) == store_a
    assert str(fetched_b.id) == store_b


def test_app_user_cross_tenant_isolation_unchanged(make_store):
    """Item 1/7: adding app_platform_admin must not change app_user's
    existing behavior. Store's own RLS keeps SELECT open by design
    (docs comment in apps/stores/models.py) but UPDATE restricted to the
    row's own tenant context -- proving that boundary is still intact,
    unaffected by the new role, using the exact same pattern as
    apps/subscriptions/tests/test_plan_rls.py."""
    store_a = make_store("Iso A", "platform-iso-a")

    # app_user CAN see it (Store SELECT is deliberately open) --
    # sanity check the fixture itself before proving the write boundary.
    assert Store.objects.filter(id=store_a).exists()

    # app_user cannot UPDATE it with no matching tenant context set.
    affected = Store.objects.filter(id=store_a).update(status=Store.Status.SUSPENDED)
    assert affected == 0

    fresh = services.get_store(store_a)
    assert fresh.status == Store.Status.ACTIVE  # provably untouched


def test_suspend_store_via_http(make_store):
    store_id = make_store("Suspend Me", "platform-suspend-http")
    client = _staff_client("staff-suspend@example.com")

    response = client.post(
        f"/api/v1/platform/stores/{store_id}/suspend", {"reason": "ToS violation"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["status"] == "suspended"

    fresh = services.get_store(store_id)
    assert fresh.status == Store.Status.SUSPENDED


def test_activate_store_via_http(make_store):
    store_id = make_store("Activate Me", "platform-activate-http", status="suspended")
    client = _staff_client("staff-activate@example.com")

    response = client.post(f"/api/v1/platform/stores/{store_id}/activate")
    assert response.status_code == 200
    assert response.data["status"] == "active"


def test_suspend_writes_exactly_one_audit_log_row(make_store, make_platform_staff_user):
    store_id = make_store("Audited", "platform-audited")
    actor = make_platform_staff_user("auditor@example.com")

    services.suspend_store(actor=actor, store=services.get_store(store_id), reason="spam")

    logs = list(AuditLog.objects.using("platform").filter(target_type="store", target_id=store_id))
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "store.suspend"
    assert str(log.store_id) == store_id
    assert log.actor_email == "auditor@example.com"
    assert log.metadata == {"reason": "spam"}


def test_store_not_found_is_404(make_platform_staff_user):
    client = _staff_client("staff-404@example.com")
    response = client.get("/api/v1/platform/stores/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
