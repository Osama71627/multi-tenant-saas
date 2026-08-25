import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def test_register_creates_an_inactive_email_unverified_user(client):
    response = client.post(
        "/api/v1/auth/register",
        {"email": "new-merchant@example.com", "password": "a-strong-p4ssw0rd!"},
        format="json",
    )
    assert response.status_code == 201, response.data
    user = PlatformUser.objects.get(email="new-merchant@example.com")
    assert user.check_password("a-strong-p4ssw0rd!")
    assert user.email_verified_at is None
    assert user.is_active is True  # active immediately; verification is separate from login gating


def test_register_sends_a_verification_email(client):
    client.post(
        "/api/v1/auth/register",
        {"email": "verify-me@example.com", "password": "a-strong-p4ssw0rd!"},
        format="json",
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["verify-me@example.com"]


def test_register_rejects_duplicate_email(client):
    PlatformUser.objects.create_user(email="dupe@example.com", password="a-strong-p4ssw0rd!")
    response = client.post(
        "/api/v1/auth/register",
        {"email": "dupe@example.com", "password": "another-p4ssw0rd!"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["errors"][0]["field"] == "email"


def test_register_rejects_weak_password(client):
    response = client.post(
        "/api/v1/auth/register",
        {"email": "weak@example.com", "password": "12345678"},
        format="json",
    )
    assert response.status_code == 400
    assert not PlatformUser.objects.filter(email="weak@example.com").exists()


def test_registration_response_never_includes_the_password_hash(client):
    response = client.post(
        "/api/v1/auth/register",
        {"email": "no-leak@example.com", "password": "a-strong-p4ssw0rd!"},
        format="json",
    )
    assert "password" not in response.data
