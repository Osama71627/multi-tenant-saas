import pytest
from django.core import mail, signing
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.accounts.services import _EMAIL_VERIFY_SALT

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(
        email="verify-flow@example.com", password="correct-h0rse!"
    )


def _extract_token() -> str:
    return mail.outbox[-1].body.split("token: ")[1].strip()


def test_registration_email_verification_token_confirms_successfully(client):
    client.post(
        "/api/v1/auth/register",
        {"email": "confirm-me@example.com", "password": "a-strong-p4ssw0rd!"},
        format="json",
    )
    token = _extract_token()

    response = client.post("/api/v1/auth/email/verify/confirm", {"token": token}, format="json")
    assert response.status_code == 200

    user = PlatformUser.objects.get(email="confirm-me@example.com")
    assert user.email_verified_at is not None


def test_tampered_token_is_rejected(client, user):
    forged = signing.dumps({"user_id": str(user.id)}, salt="wrong-salt")
    response = client.post("/api/v1/auth/email/verify/confirm", {"token": forged}, format="json")
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.email_verified_at is None


def test_expired_token_is_rejected(client, user):
    with freeze_time("2020-01-01"):
        token = signing.dumps({"user_id": str(user.id)}, salt=_EMAIL_VERIFY_SALT)
    response = client.post("/api/v1/auth/email/verify/confirm", {"token": token}, format="json")
    assert response.status_code == 400


def test_resend_requires_authentication(client):
    response = client.post("/api/v1/auth/email/verify/resend", {}, format="json")
    assert response.status_code == 401


def test_resend_is_a_noop_if_already_verified(client, user):
    from django.utils import timezone

    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])

    login = client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    mail.outbox.clear()
    response = client.post("/api/v1/auth/email/verify/resend", {}, format="json")
    assert response.status_code == 200
    assert len(mail.outbox) == 0
