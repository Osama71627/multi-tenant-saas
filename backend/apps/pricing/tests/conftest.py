import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services


def make_client_for(
    email: str, password: str = "correct-h0rse!"  # noqa: S107
) -> tuple[APIClient, PlatformUser]:
    user = PlatformUser.objects.create_user(email=email, password=password)
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client, user


@pytest.fixture
def owner_client_and_store():
    client, owner = make_client_for("pricing-owner@example.com")
    store = store_services.create_store(owner=owner, name="Pricing Co", slug="pricing-co")
    return client, owner, store
