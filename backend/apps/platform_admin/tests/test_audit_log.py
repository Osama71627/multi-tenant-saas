"""
Required proof (approval section 9): AuditLog is genuinely append-only,
enforced at the DB grant level (not just "no UI button for it"), and
`app_user` can never read a single row -- both proven against real
PostgreSQL, not simulated.
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, connection
from django.db import transaction as django_transaction

from apps.platform_admin import services
from apps.platform_admin.models import AuditLog

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def test_suspend_writes_a_readable_audit_log_entry(make_store, make_platform_staff_user):
    store_id = make_store("Audit Read", "platform-audit-read")
    actor = make_platform_staff_user("audit1@example.com")

    services.suspend_store(actor=actor, store=services.get_store(store_id), reason="test")

    logs = list(services.list_audit_logs(target_type="store", target_id=store_id))
    assert len(logs) == 1
    assert logs[0].action == "store.suspend"


def test_app_platform_admin_cannot_update_an_audit_log_row(make_store, make_platform_staff_user):
    store_id = make_store("Audit NoUpdate", "platform-audit-noupdate")
    actor = make_platform_staff_user("audit2@example.com")
    services.suspend_store(actor=actor, store=services.get_store(store_id), reason="test")
    log = services.list_audit_logs(target_type="store", target_id=store_id).first()

    with pytest.raises(DatabaseError):
        with django_transaction.atomic(using="platform"):
            AuditLog.objects.using("platform").filter(id=log.id).update(action="tampered")


def test_app_platform_admin_cannot_delete_an_audit_log_row(make_store, make_platform_staff_user):
    store_id = make_store("Audit NoDelete", "platform-audit-nodelete")
    actor = make_platform_staff_user("audit3@example.com")
    services.suspend_store(actor=actor, store=services.get_store(store_id), reason="test")
    log = services.list_audit_logs(target_type="store", target_id=store_id).first()

    with pytest.raises(DatabaseError):
        with django_transaction.atomic(using="platform"):
            AuditLog.objects.using("platform").filter(id=log.id).delete()


def test_app_user_cannot_read_audit_log_at_all(make_store, make_platform_staff_user):
    """RLS on `platform_admin_auditlog` has ZERO policies for any
    command, SELECT included -- `app_user` sees nothing, no matter what
    table-level GRANT it might have inherited from the blanket
    `apps.tenancy.privileges` hook."""
    store_id = make_store("Audit AppUser", "platform-audit-appuser")
    actor = make_platform_staff_user("audit4@example.com")
    services.suspend_store(actor=actor, store=services.get_store(store_id), reason="test")

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM platform_admin_auditlog")
        (count,) = cursor.fetchone()
    assert count == 0


def test_rls_is_enabled_on_audit_log_table():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = %s", ["platform_admin_auditlog"]
        )
        (enabled,) = cursor.fetchone()
    assert enabled is True


def test_audit_log_endpoint_is_read_only(make_store, make_platform_staff_user):
    """No POST/PUT/PATCH/DELETE route exists for `/platform/audit-logs`
    at all -- only GET. A stray write attempt 404s/405s at the URL
    routing layer, before it could ever reach the DB."""
    from apps.platform_admin.tests.mfa_test_helpers import create_and_authenticate_platform_staff

    client = create_and_authenticate_platform_staff("audit-http@example.com")

    response = client.post("/api/v1/platform/audit-logs", {}, format="json")
    assert response.status_code == 405
