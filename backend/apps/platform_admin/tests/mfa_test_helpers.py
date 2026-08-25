"""
Shared test helper for authenticating as a platform-staff user through
the real Phase 17 two-step MFA login (password -> challenge -> TOTP
enroll/confirm -> JWT carrying `mfa=True`). Every platform_admin test
that needs an authenticated staff `APIClient` goes through this:
`IsPlatformStaff` (apps.platform_admin.permissions) now requires that
token claim, so the old one-step "log in, grab `access`" pattern no
longer reaches any `/api/v1/platform/*` endpoint.
"""

from __future__ import annotations

import pyotp
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser

DEFAULT_PASSWORD = "correct-h0rse!"  # noqa: S105 -- test fixture, not a secret


def create_and_authenticate_platform_staff(
    email: str = "staff@example.com", *, password: str = DEFAULT_PASSWORD
) -> APIClient:
    PlatformUser.objects.create_user(email=email, password=password, is_platform_staff=True)
    client = APIClient()

    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    assert login.status_code == 200, login.data
    assert login.data["state"] == "mfa_setup_required", login.data
    challenge_token = login.data["challenge_token"]

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
    assert confirm.status_code == 200, confirm.data

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {confirm.data['access']}")
    return client
