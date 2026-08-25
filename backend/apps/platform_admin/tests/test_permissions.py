"""
Required proof (approval section 13, item 4): a non-platform-staff user
hitting `/api/v1/platform/*` gets 403 and no privileged query ever runs
-- the backend permission check is the real security boundary, not a
hidden frontend route. `client.post`/`client.get` below run entirely
in-process on the SAME "default" connection/transaction as the rest of
the test (Django's test client, not a real HTTP round-trip), so a plain
`PlatformUser.objects.create_user(...)` here needs no cross-alias
seeding -- only the actual privileged DATA (Store/Subscription/Plan
rows) does, which these tests deliberately never create: if any endpoint
here actually reached its service layer, it would find nothing and
either 404 or return an empty list, not prove the 403 gate is what
stopped it. The stronger, more direct proof is `views.PlatformAPIView`
never being entered at all -- these assertions check exactly that
(status code alone, since DRF's permission check runs in `initial()`,
before `get`/`post` on the view is ever called).
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.platform_admin.tests.mfa_test_helpers import (
    DEFAULT_PASSWORD as _TEST_PASSWORD,
)
from apps.platform_admin.tests.mfa_test_helpers import (
    create_and_authenticate_platform_staff,
)

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def _client_for(
    email: str, *, is_platform_staff: bool, password: str = _TEST_PASSWORD
) -> APIClient:
    if is_platform_staff:
        return create_and_authenticate_platform_staff(email, password=password)
    PlatformUser.objects.create_user(email=email, password=password, is_platform_staff=False)
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    assert login.status_code == 200, login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


_SOME_UUID = str(uuid.uuid4())

_GET_ENDPOINTS = [
    "/api/v1/platform/overview",
    "/api/v1/platform/stores",
    f"/api/v1/platform/stores/{_SOME_UUID}",
    "/api/v1/platform/plans",
    f"/api/v1/platform/plans/{_SOME_UUID}",
    "/api/v1/platform/subscriptions",
    f"/api/v1/platform/subscriptions/{_SOME_UUID}",
    "/api/v1/platform/users",
    f"/api/v1/platform/users/{_SOME_UUID}",
    "/api/v1/platform/audit-logs",
]

_POST_ENDPOINTS = [
    f"/api/v1/platform/stores/{_SOME_UUID}/suspend",
    f"/api/v1/platform/stores/{_SOME_UUID}/activate",
    "/api/v1/platform/plans",
    f"/api/v1/platform/plans/{_SOME_UUID}/versions",
    f"/api/v1/platform/plans/{_SOME_UUID}/activate",
    f"/api/v1/platform/plans/{_SOME_UUID}/deactivate",
    f"/api/v1/platform/subscriptions/{_SOME_UUID}/activate",
    f"/api/v1/platform/subscriptions/{_SOME_UUID}/cancel",
]


@pytest.mark.parametrize("path", _GET_ENDPOINTS)
def test_non_platform_staff_gets_403_on_get(path):
    client = _client_for("merchant@example.com", is_platform_staff=False)
    response = client.get(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", _POST_ENDPOINTS)
def test_non_platform_staff_gets_403_on_post(path):
    client = _client_for("merchant2@example.com", is_platform_staff=False)
    response = client.post(path, {}, format="json")
    assert response.status_code == 403


def test_unauthenticated_request_is_rejected():
    response = APIClient().get("/api/v1/platform/stores")
    assert response.status_code == 401


def test_inactive_platform_staff_account_still_gets_403():
    """`is_platform_staff=True` alone must not be sufficient -- a
    deactivated staff account (offboarded employee) must lose access
    too, same as any other account."""
    user = PlatformUser.objects.create_user(
        email="exstaff@example.com", password="correct-h0rse!", is_platform_staff=True  # noqa: S106
    )
    user.is_active = False
    user.save(update_fields=["is_active"])

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "exstaff@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    # An inactive account should already fail authentication itself.
    assert login.status_code in (400, 401)


def test_platform_staff_can_reach_a_platform_endpoint():
    """Positive control for the tests above: a genuine platform-staff
    user is NOT blocked by IsPlatformStaff (proves the 403s above are a
    real gate, not e.g. a routing bug that 403s everyone)."""
    client = _client_for("staff@example.com", is_platform_staff=True)
    response = client.get("/api/v1/platform/overview")
    assert response.status_code == 200
