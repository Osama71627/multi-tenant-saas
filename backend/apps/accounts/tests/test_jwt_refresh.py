"""
Proves refresh-token rotation, single-token reuse rejection, and --
critically -- the *family* invalidation apps/accounts/tokens.py adds on
top of SimpleJWT's default rotate+blacklist behavior. See that module's
docstring for the exact threat this defends against.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(
        email="refresh-user@example.com", password="correct-h0rse!"
    )


def _login(client, user):
    response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    assert response.status_code == 200
    return response.data["access"], response.data["refresh"]


def test_refresh_rotates_and_returns_a_new_pair(client, user):
    _access, refresh1 = _login(client, user)
    response = client.post("/api/v1/auth/refresh", {"refresh": refresh1}, format="json")
    assert response.status_code == 200
    assert "access" in response.data
    assert response.data["refresh"] != refresh1


def test_reusing_an_already_rotated_refresh_token_is_rejected(client, user):
    _access, refresh1 = _login(client, user)
    client.post("/api/v1/auth/refresh", {"refresh": refresh1}, format="json")  # rotates refresh1

    reuse_response = client.post("/api/v1/auth/refresh", {"refresh": refresh1}, format="json")
    assert reuse_response.status_code == 401


def test_reuse_invalidates_the_whole_token_family_not_just_the_reused_token(client, user):
    """
    The actual security property: an attacker replaying a stolen-but-
    already-rotated refresh token doesn't just fail themselves -- it
    forces the legitimate user's OTHER still-valid refresh token to stop
    working too, because at that point neither party can be trusted to
    be the legitimate holder. Full re-login is required everywhere.
    """
    _access, refresh1 = _login(client, user)
    rotate_response = client.post("/api/v1/auth/refresh", {"refresh": refresh1}, format="json")
    refresh2 = rotate_response.data["refresh"]

    # Reuse of the now-rotated refresh1 triggers family invalidation.
    reuse_response = client.post("/api/v1/auth/refresh", {"refresh": refresh1}, format="json")
    assert reuse_response.status_code == 401

    # refresh2 was completely valid and unused up to this point -- it
    # must now ALSO be rejected.
    still_valid_response = client.post("/api/v1/auth/refresh", {"refresh": refresh2}, format="json")
    assert still_valid_response.status_code == 401


def test_family_invalidation_is_scoped_to_the_affected_user_only(client, user):
    other_user = PlatformUser.objects.create_user(
        email="other-refresh-user@example.com", password="correct-h0rse!"
    )
    _access_a, refresh_a1 = _login(client, user)
    _access_b, refresh_b1 = _login(client, other_user)

    client.post(
        "/api/v1/auth/refresh", {"refresh": refresh_a1}, format="json"
    )  # rotates refresh_a1
    # Reusing the now-rotated token triggers family invalidation for `user` only.
    client.post("/api/v1/auth/refresh", {"refresh": refresh_a1}, format="json")

    # `other_user`'s independent refresh token must be unaffected.
    other_response = client.post("/api/v1/auth/refresh", {"refresh": refresh_b1}, format="json")
    assert other_response.status_code == 200
