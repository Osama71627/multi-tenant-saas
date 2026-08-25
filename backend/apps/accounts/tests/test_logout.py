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
        email="logout-user@example.com", password="correct-h0rse!"
    )


def _login(client, user):
    response = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    return response.data["access"], response.data["refresh"]


def test_logout_requires_authentication(client):
    response = client.post("/api/v1/auth/logout", {"refresh": "irrelevant"}, format="json")
    assert response.status_code == 401


def test_logout_blacklists_the_refresh_token(client, user):
    access, refresh = _login(client, user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = client.post("/api/v1/auth/logout", {"refresh": refresh}, format="json")
    assert response.status_code == 204

    reuse_response = APIClient().post("/api/v1/auth/refresh", {"refresh": refresh}, format="json")
    assert reuse_response.status_code == 401


def test_logout_without_a_refresh_token_is_a_client_error_not_a_500(client, user):
    access, _refresh = _login(client, user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = client.post("/api/v1/auth/logout", {}, format="json")
    assert response.status_code == 400
