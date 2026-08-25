"""
Phase 17 required proofs: platform-staff login never issues a JWT before
a second factor succeeds, ordinary accounts are unaffected, wrong/missing
codes never grant access, and a token minted before MFA completed can
never reach a platform endpoint even after later promotion -- see
apps.accounts.mfa_services' module docstring for the approved design.
"""

from __future__ import annotations

import pyotp
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import MfaChallenge, MfaRecoveryCode, MfaTotpDevice, PlatformUser
from apps.accounts.tokens import PlatformTokenObtainPairSerializer

pytestmark = pytest.mark.django_db

_PASSWORD = "correct-h0rse!"  # noqa: S105 -- test fixture, not a secret


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def staff_user() -> PlatformUser:
    return PlatformUser.objects.create_user(
        email="staff@example.com", password=_PASSWORD, is_platform_staff=True
    )


@pytest.fixture
def merchant_user() -> PlatformUser:
    return PlatformUser.objects.create_user(email="merchant@example.com", password=_PASSWORD)


def _login(client: APIClient, email: str, password: str = _PASSWORD):
    return client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")


def _enroll(client: APIClient, challenge_token: str) -> tuple[str, dict]:
    start = client.post(
        "/api/v1/auth/mfa/enroll/start", {"challenge_token": challenge_token}, format="json"
    )
    assert start.status_code == 200, start.data
    code = pyotp.TOTP(start.data["secret"]).now()
    confirm = client.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": challenge_token, "code": code},
        format="json",
    )
    return start.data["secret"], confirm.data


# --------------------------------------------------------------------------
# Ordinary (non-platform-staff) accounts: completely unaffected.
# --------------------------------------------------------------------------


def test_merchant_login_is_single_step_and_carries_mfa_false_claim(client, merchant_user):
    response = _login(client, merchant_user.email)
    assert response.status_code == 200
    assert "access" in response.data and "refresh" in response.data
    token = AccessToken(response.data["access"])
    assert token["mfa"] is False


# --------------------------------------------------------------------------
# Platform staff, not yet enrolled.
# --------------------------------------------------------------------------


def test_staff_login_without_enrollment_returns_setup_state_and_no_tokens(client, staff_user):
    response = _login(client, staff_user.email)
    assert response.status_code == 200
    assert response.data["state"] == "mfa_setup_required"
    assert "challenge_token" in response.data
    assert "access" not in response.data
    assert "refresh" not in response.data


def test_wrong_password_for_staff_account_is_rejected_before_any_challenge(client, staff_user):
    response = client.post(
        "/api/v1/auth/login", {"email": staff_user.email, "password": "wrong"}, format="json"
    )
    assert response.status_code == 401
    assert MfaChallenge.objects.filter(user=staff_user).count() == 0


# --------------------------------------------------------------------------
# Enrollment.
# --------------------------------------------------------------------------


def test_enroll_confirm_with_correct_code_issues_tokens_and_recovery_codes(client, staff_user):
    login = _login(client, staff_user.email)
    _secret, confirm_data = _enroll(client, login.data["challenge_token"])

    assert "access" in confirm_data and "refresh" in confirm_data
    assert len(confirm_data["recovery_codes"]) == 8
    token = AccessToken(confirm_data["access"])
    assert token["mfa"] is True

    device = MfaTotpDevice.objects.get(user=staff_user)
    assert device.is_confirmed
    assert MfaRecoveryCode.objects.filter(user=staff_user).count() == 8


def test_recovery_codes_are_never_stored_raw(client, staff_user):
    login = _login(client, staff_user.email)
    _secret, confirm_data = _enroll(client, login.data["challenge_token"])
    raw_codes = set(confirm_data["recovery_codes"])
    stored_hashes = set(
        MfaRecoveryCode.objects.filter(user=staff_user).values_list("code_hash", flat=True)
    )
    assert not (raw_codes & stored_hashes)


def test_enroll_confirm_with_wrong_code_issues_nothing(client, staff_user):
    login = _login(client, staff_user.email)
    client.post(
        "/api/v1/auth/mfa/enroll/start",
        {"challenge_token": login.data["challenge_token"]},
        format="json",
    )
    confirm = client.post(
        "/api/v1/auth/mfa/enroll/confirm",
        {"challenge_token": login.data["challenge_token"], "code": "000000"},
        format="json",
    )
    assert confirm.status_code == 401
    assert "access" not in confirm.data
    device = MfaTotpDevice.objects.get(user=staff_user)
    assert not device.is_confirmed


def test_totp_secret_is_never_stored_raw_in_the_device_row(client, staff_user):
    login = _login(client, staff_user.email)
    secret, _confirm_data = _enroll(client, login.data["challenge_token"])
    device = MfaTotpDevice.objects.get(user=staff_user)
    assert secret not in device.secret_encrypted
    assert device.secret_encrypted.startswith("v1:")


# --------------------------------------------------------------------------
# Login once already enrolled.
# --------------------------------------------------------------------------


@pytest.fixture
def enrolled_staff_client_state(client, staff_user):
    login = _login(client, staff_user.email)
    secret, _confirm_data = _enroll(client, login.data["challenge_token"])
    return secret


def test_second_login_after_enrollment_returns_mfa_required_state(
    client, staff_user, enrolled_staff_client_state
):
    response = _login(client, staff_user.email)
    assert response.status_code == 200
    assert response.data["state"] == "mfa_required"
    assert "access" not in response.data


def test_verify_with_correct_totp_issues_tokens(client, staff_user, enrolled_staff_client_state):
    secret = enrolled_staff_client_state
    login = _login(client, staff_user.email)
    code = pyotp.TOTP(secret).now()
    response = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": login.data["challenge_token"], "code": code},
        format="json",
    )
    assert response.status_code == 200
    token = AccessToken(response.data["access"])
    assert token["mfa"] is True
    assert token["aud"] == "platform"


def test_verify_with_wrong_totp_is_rejected(client, staff_user, enrolled_staff_client_state):
    login = _login(client, staff_user.email)
    response = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": login.data["challenge_token"], "code": "000000"},
        format="json",
    )
    assert response.status_code == 401
    assert "access" not in response.data


def test_challenge_is_single_use(client, staff_user, enrolled_staff_client_state):
    secret = enrolled_staff_client_state
    login = _login(client, staff_user.email)
    code = pyotp.TOTP(secret).now()
    first = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": login.data["challenge_token"], "code": code},
        format="json",
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": login.data["challenge_token"], "code": code},
        format="json",
    )
    assert second.status_code == 401


def test_challenge_locks_after_max_failed_attempts(client, staff_user, enrolled_staff_client_state):
    login = _login(client, staff_user.email)
    challenge_token = login.data["challenge_token"]
    for _ in range(MfaChallenge.MAX_ATTEMPTS):
        response = client.post(
            "/api/v1/auth/mfa/verify",
            {"challenge_token": challenge_token, "code": "000000"},
            format="json",
        )
        assert response.status_code == 401

    secret = enrolled_staff_client_state
    correct_code = pyotp.TOTP(secret).now()
    still_locked = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": challenge_token, "code": correct_code},
        format="json",
    )
    assert still_locked.status_code == 401


def test_expired_challenge_is_rejected(client, staff_user, enrolled_staff_client_state):
    secret = enrolled_staff_client_state
    login = _login(client, staff_user.email)
    challenge = MfaChallenge.objects.get(user=staff_user, used_at__isnull=True)
    challenge.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    challenge.save(update_fields=["expires_at"])

    code = pyotp.TOTP(secret).now()
    response = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": login.data["challenge_token"], "code": code},
        format="json",
    )
    assert response.status_code == 401


def test_recovery_code_login_end_to_end(client, staff_user):
    login = _login(client, staff_user.email)
    _secret, confirm_data = _enroll(client, login.data["challenge_token"])
    raw_recovery_code = confirm_data["recovery_codes"][0]

    second_login = _login(client, staff_user.email)
    response = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": second_login.data["challenge_token"], "code": raw_recovery_code},
        format="json",
    )
    assert response.status_code == 200
    token = AccessToken(response.data["access"])
    assert token["mfa"] is True

    # Same code cannot be used twice.
    third_login = _login(client, staff_user.email)
    reuse = client.post(
        "/api/v1/auth/mfa/verify",
        {"challenge_token": third_login.data["challenge_token"], "code": raw_recovery_code},
        format="json",
    )
    assert reuse.status_code == 401


# --------------------------------------------------------------------------
# Password reset must not silently disable MFA.
# --------------------------------------------------------------------------


def test_password_reset_does_not_touch_mfa_enrollment(
    client, staff_user, enrolled_staff_client_state
):
    from apps.accounts import services as accounts_services
    from apps.accounts.models import PasswordResetToken

    _token, raw_token = PasswordResetToken.issue(staff_user)
    accounts_services.confirm_password_reset(token=raw_token, new_password="new-correct-h0rse!")

    device = MfaTotpDevice.objects.get(user=staff_user)
    assert device.is_confirmed
    assert MfaRecoveryCode.objects.filter(user=staff_user).count() == 8

    # Login now requires the (unchanged) MFA challenge again, not a
    # single-step token issuance.
    response = client.post(
        "/api/v1/auth/login",
        {"email": staff_user.email, "password": "new-correct-h0rse!"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["state"] == "mfa_required"


# --------------------------------------------------------------------------
# Token-claim invariant: IsPlatformStaff checks the token, not just the
# live DB flag -- a token minted before MFA completed (or before a user
# was even staff) must never reach a platform endpoint.
# --------------------------------------------------------------------------


def test_token_without_mfa_claim_cannot_reach_a_platform_endpoint(client, staff_user):
    """Simulates a token minted by the plain (non-MFA) path -- e.g. a
    stale token from before this user was promoted to platform staff."""
    token = PlatformTokenObtainPairSerializer.get_token(staff_user)
    assert token["mfa"] is False
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token!s}")
    response = client.get("/api/v1/platform/overview")
    assert response.status_code == 403


def test_promotion_mid_session_does_not_grant_platform_access_without_mfa(client, merchant_user):
    """A merchant logs in normally (mfa=False token, correctly -- they
    aren't staff yet), then gets promoted. The already-issued token must
    stay locked out of /platform/* until they log out and back in through
    the full MFA flow."""
    login = _login(client, merchant_user.email)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    merchant_user.is_platform_staff = True
    merchant_user.save(update_fields=["is_platform_staff"])

    response = client.get("/api/v1/platform/overview")
    assert response.status_code == 403
