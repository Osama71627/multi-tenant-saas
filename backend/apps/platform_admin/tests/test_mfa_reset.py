"""
Phase 17 approved constraint: resetting another platform-staff account's
MFA must be an explicit, audited privileged action -- never a
self-service bypass. See apps.platform_admin.services.reset_user_mfa.

`reset_user_mfa` reads/writes through the "platform" alias
(`app_platform_admin`) for everything, including the AuditLog row, in one
atomic block -- matching every other privileged mutation in this module.
pytest-django gives each declared alias its own uncommitted per-test
transaction, so test fixtures for both the target user AND their MFA
enrollment need real, committed rows (via the migrator connection) to be
visible there -- same proven pattern as apps/platform_admin/tests/
conftest.py's `make_store`/`make_platform_staff_user`.
"""

from __future__ import annotations

import psycopg
import pytest
from django.contrib.auth.hashers import make_password
from django.db import connections

from apps.accounts import encryption as accounts_encryption
from apps.accounts import mfa as accounts_mfa
from apps.accounts.models import MfaRecoveryCode, MfaTotpDevice, PlatformUser
from apps.core.uuid7 import uuid7
from apps.platform_admin.models import AuditLog
from apps.platform_admin.tests.mfa_test_helpers import create_and_authenticate_platform_staff

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def _migrator_conn() -> psycopg.Connection:
    params = connections["migrator"].get_connection_params()
    return psycopg.connect(**params, autocommit=True)


def _create_committed_staff_user(email: str, password: str) -> PlatformUser:
    user_id = str(uuid7())
    with _migrator_conn() as conn:
        conn.execute(
            "INSERT INTO accounts_platformuser "
            "(id, created_at, updated_at, password, last_login, email, full_name, "
            "is_active, is_staff, is_platform_staff, is_superuser, email_verified_at) "
            "VALUES (%s, now(), now(), %s, NULL, %s, '', true, false, true, false, NULL)",
            [user_id, make_password(password), email],
        )
    return PlatformUser.objects.get(id=user_id)


def _commit_confirmed_mfa_enrollment(user_id: str, *, recovery_code_count: int = 8) -> None:
    with _migrator_conn() as conn:
        conn.execute(
            "INSERT INTO accounts_mfatotpdevice "
            "(created_at, updated_at, user_id, secret_encrypted, confirmed_at) "
            "VALUES (now(), now(), %s, %s, now())",
            [user_id, accounts_encryption.encrypt_secret(accounts_mfa.generate_totp_secret())],
        )
        for code in accounts_mfa.generate_recovery_codes(count=recovery_code_count):
            conn.execute(
                "INSERT INTO accounts_mfarecoverycode "
                "(id, created_at, updated_at, user_id, code_hash, used_at) "
                "VALUES (%s, now(), now(), %s, %s, NULL)",
                [str(uuid7()), user_id, accounts_mfa.hash_recovery_code(code)],
            )


def test_mfa_reset_revokes_device_and_recovery_codes_and_writes_audit_log():
    """UPDATE, not DELETE -- `app_platform_admin` has no DELETE grant on
    either table (apps.platform_admin.privileges), same posture as every
    other privileged mutation in this module."""
    victim = _create_committed_staff_user("locked-out-staff@example.com", "correct-h0rse!")
    _commit_confirmed_mfa_enrollment(str(victim.id))
    old_secret = MfaTotpDevice.objects.using("platform").get(user=victim).secret_encrypted
    assert (
        MfaTotpDevice.objects.using("platform")
        .filter(user=victim, confirmed_at__isnull=False)
        .exists()
    )
    unused_codes = MfaRecoveryCode.objects.using("platform").filter(
        user=victim, used_at__isnull=True
    )
    assert unused_codes.count() == 8

    admin_client = create_and_authenticate_platform_staff("mfa-admin@example.com")
    response = admin_client.post(f"/api/v1/platform/users/{victim.id}/mfa/reset")
    assert response.status_code == 204

    device = MfaTotpDevice.objects.using("platform").get(user=victim)
    assert device.confirmed_at is None
    assert device.secret_encrypted != old_secret
    assert unused_codes.count() == 0
    assert MfaRecoveryCode.objects.using("platform").filter(user=victim).count() == 8

    log = AuditLog.objects.using("platform").get(target_type="platform_user", target_id=victim.id)
    assert log.action == "user.mfa_reset"


def test_mfa_reset_requires_platform_staff():
    from rest_framework.test import APIClient

    victim = PlatformUser.objects.create_user(
        email="another-staff@example.com",
        password="correct-h0rse!",  # noqa: S106
        is_platform_staff=True,
    )
    non_staff = PlatformUser.objects.create_user(
        email="regular-merchant@example.com", password="correct-h0rse!"  # noqa: S106
    )
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": non_staff.email, "password": "correct-h0rse!"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = client.post(f"/api/v1/platform/users/{victim.id}/mfa/reset")
    assert response.status_code == 403


def test_after_reset_victim_has_no_confirmed_device_for_next_login():
    """`mfa_services.enrollment_state` (what `LoginView` calls to decide
    between `mfa_required`/`mfa_setup_required`) must see `mfa_setup_
    required` again right after a reset -- checked via the SAME "platform"
    alias the reset itself mutated through (a real HTTP round-trip through
    `/auth/login` would instead read via "default", which pytest-django's
    per-alias transaction isolation can't make see this test's "platform"-
    side mutation -- see this file's module docstring)."""
    from apps.accounts import mfa_services

    victim = _create_committed_staff_user("re-enroll-staff@example.com", "correct-h0rse!")
    _commit_confirmed_mfa_enrollment(str(victim.id))

    admin_client = create_and_authenticate_platform_staff("mfa-admin-2@example.com")
    reset_response = admin_client.post(f"/api/v1/platform/users/{victim.id}/mfa/reset")
    assert reset_response.status_code == 204

    victim_via_platform = PlatformUser.objects.using("platform").get(id=victim.id)
    assert mfa_services.enrollment_state(victim_via_platform) == "mfa_setup_required"
