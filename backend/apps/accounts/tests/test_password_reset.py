from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetToken, PlatformUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(
        email="reset-user@example.com", password="old-p4ssword!"
    )


def test_reset_request_response_is_identical_for_existing_and_nonexistent_email(client, user):
    """Anti user-enumeration -- docs/ARCHITECTURE.md section 6.3."""
    real = client.post("/api/v1/auth/password/reset", {"email": user.email}, format="json")
    fake = client.post(
        "/api/v1/auth/password/reset", {"email": "nobody@example.com"}, format="json"
    )
    assert real.status_code == fake.status_code == 200
    assert real.data == fake.data


def test_reset_request_for_existing_user_sends_an_email_and_creates_a_token(client, user):
    client.post("/api/v1/auth/password/reset", {"email": user.email}, format="json")
    assert len(mail.outbox) == 1
    assert PasswordResetToken.objects.filter(user=user).count() == 1


def test_reset_request_for_nonexistent_user_sends_no_email(client):
    client.post("/api/v1/auth/password/reset", {"email": "nobody@example.com"}, format="json")
    assert len(mail.outbox) == 0


def _issue_and_extract_token(user) -> str:
    from apps.accounts import services

    mail.outbox.clear()
    services.request_password_reset(email=user.email)
    body = mail.outbox[0].body
    return body.split("token: ")[1].strip()


def test_confirm_resets_the_password(client, user):
    raw_token = _issue_and_extract_token(user)
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": raw_token, "new_password": "brand-new-p4ssword!"},
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("brand-new-p4ssword!")
    assert not user.check_password("old-p4ssword!")


def test_confirm_is_single_use(client, user):
    raw_token = _issue_and_extract_token(user)
    first = client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": raw_token, "new_password": "brand-new-p4ssword!"},
        format="json",
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": raw_token, "new_password": "yet-another-p4ssword!"},
        format="json",
    )
    assert second.status_code == 400
    user.refresh_from_db()
    assert user.check_password("brand-new-p4ssword!")  # unchanged by the rejected second attempt


def test_confirm_rejects_an_expired_token(client, user):
    raw_token = _issue_and_extract_token(user)
    PasswordResetToken.objects.filter(user=user).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": raw_token, "new_password": "brand-new-p4ssword!"},
        format="json",
    )
    assert response.status_code == 400


def test_confirm_rejects_a_garbage_token(client):
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": "not-a-real-token", "new_password": "brand-new-p4ssword!"},
        format="json",
    )
    assert response.status_code == 400


def test_confirm_enforces_password_strength(client, user):
    raw_token = _issue_and_extract_token(user)
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": raw_token, "new_password": "12345678"},
        format="json",
    )
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password("old-p4ssword!")


def test_confirm_invalidates_all_other_active_sessions(client, user):
    login = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "old-p4ssword!"}, format="json"
    )
    old_refresh = login.data["refresh"]

    raw_token = _issue_and_extract_token(user)
    client.post(
        "/api/v1/auth/password/reset/confirm",
        {"token": raw_token, "new_password": "brand-new-p4ssword!"},
        format="json",
    )

    reuse_response = APIClient().post(
        "/api/v1/auth/refresh", {"refresh": old_refresh}, format="json"
    )
    assert reuse_response.status_code == 401


def test_reset_token_is_never_stored_in_plaintext(user):
    from apps.accounts import services

    services.request_password_reset(email=user.email)
    token = PasswordResetToken.objects.get(user=user)
    assert len(token.token_hash) == 64  # sha256 hex digest
    assert mail.outbox[0].body.split("token: ")[1].strip() != token.token_hash
