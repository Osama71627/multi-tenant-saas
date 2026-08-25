import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts import lockout
from apps.accounts.models import PlatformUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(
        email="login-user@example.com", password="correct-h0rse!"
    )


def test_login_succeeds_with_correct_credentials(client, user):
    response = client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": "correct-h0rse!"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_access_token_carries_platform_audience_claim(client, user):
    response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    token = AccessToken(response.data["access"])
    assert token["aud"] == "platform"


def test_access_token_never_embeds_permissions_or_role_claims(client, user):
    """
    docs/ARCHITECTURE.md section 6.2: permissions must be resolved fresh
    from the DB on every request, never trusted from the token, so that
    revoking a permission takes effect immediately rather than after the
    15-minute access token TTL.
    """
    response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    token = AccessToken(response.data["access"])
    for forbidden_claim in ("role", "permissions", "is_platform_staff", "memberships"):
        assert forbidden_claim not in token.payload


def test_login_fails_with_wrong_password(client, user):
    response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "wrong"}, format="json"
    )
    assert response.status_code == 401


def test_login_fails_for_nonexistent_email(client):
    response = client.post(
        "/api/v1/auth/login",
        {"email": "nobody@example.com", "password": "whatever12345"},
        format="json",
    )
    assert response.status_code == 401


def test_login_fails_for_inactive_user(client):
    user = PlatformUser.objects.create_user(email="inactive@example.com", password="correct-h0rse!")
    user.is_active = False
    user.save(update_fields=["is_active"])
    response = client.post(
        "/api/v1/auth/login",
        {"email": "inactive@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    assert response.status_code == 401


def test_repeated_failed_logins_lock_the_account(client, user):
    for _ in range(lockout.THRESHOLD):
        response = client.post(
            "/api/v1/auth/login", {"email": user.email, "password": "wrong"}, format="json"
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": "correct-h0rse!"},  # even the RIGHT password
        format="json",
    )
    assert locked_response.status_code == 429


def test_successful_login_clears_the_failure_counter(client, user):
    for _ in range(lockout.THRESHOLD - 1):
        client.post("/api/v1/auth/login", {"email": user.email, "password": "wrong"}, format="json")

    ok_response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    assert ok_response.status_code == 200

    # The counter reset -- one more failure afterwards should NOT lock yet.
    fail_response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "wrong"}, format="json"
    )
    assert fail_response.status_code == 401  # not 429
