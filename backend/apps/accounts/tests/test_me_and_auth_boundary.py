"""
`/auth/me` + the JWT audience boundary. Also proves the "expired token
rejected" and "tampered signature rejected" security properties called
for by docs/DECISIONS.md governance point 16 explicitly (JWT tests).
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import PlatformUser

pytestmark = pytest.mark.django_db


def _minutes_ago(minutes: int):
    return timezone.now() - timedelta(minutes=minutes)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(
        email="me-user@example.com", password="correct-h0rse!", full_name="Me User"
    )


def _login(client, user):
    response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    return response.data["access"]


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_the_authenticated_users_identity(client, user):
    access = _login(client, user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["full_name"] == "Me User"
    assert "password" not in response.data


def test_me_never_leaks_another_users_identity(client, user):
    other = PlatformUser.objects.create_user(
        email="other-me@example.com", password="correct-h0rse!"
    )
    access = _login(client, other)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = client.get("/api/v1/auth/me")
    assert response.data["email"] == other.email
    assert response.data["email"] != user.email


def test_expired_access_token_is_rejected(client, user):
    with freeze_time(_minutes_ago(20)):
        access = _login(client, user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_tampered_access_token_is_rejected(client, user):
    access = _login(client, user)
    tampered = access[:-4] + ("A" if access[-4] != "A" else "B") + access[-3:]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered}")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_a_non_platform_audience_token_is_rejected(client, user):
    """
    Simulates a token from a different realm (e.g. a future storefront/
    customer JWT) -- must never authenticate as a platform user, even
    with a perfectly valid signature and a real user id.
    """
    refresh = RefreshToken.for_user(user)
    refresh["aud"] = "storefront"
    access = str(refresh.access_token)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
