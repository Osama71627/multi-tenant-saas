"""
Phase 12 (dashboard store switcher): `GET /api/v1/dashboard/stores`
lists only stores the current user has an ACTIVE membership in -- a
deliberate cross-tenant read (apps.stores.services.list_stores_for_user),
proven here to still be correctly scoped to the CALLING user only.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores.services import create_store

pytestmark = pytest.mark.django_db


def _client_for(email: str) -> APIClient:
    PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login", {"email": email, "password": "correct-h0rse!"}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


def test_unauthenticated_request_cannot_list_stores():
    response = APIClient().get("/api/v1/dashboard/stores")
    assert response.status_code == 401


def test_a_user_with_no_stores_gets_an_empty_list():
    client = _client_for("no-stores@example.com")
    response = client.get("/api/v1/dashboard/stores")
    assert response.status_code == 200
    assert response.data == []


def test_lists_only_stores_the_user_owns_not_other_users_stores():
    owner = PlatformUser.objects.create_user(
        email="list-owner@example.com", password="correct-h0rse!"
    )  # noqa: S106
    create_store(owner=owner, name="Mine Co", slug="list-mine-co")

    other_client = _client_for("list-other@example.com")
    response = other_client.get("/api/v1/dashboard/stores")
    assert response.status_code == 200
    assert response.data == []


def test_lists_the_users_own_stores_with_expected_fields():
    owner = PlatformUser.objects.create_user(
        email="list-owner-2@example.com", password="correct-h0rse!"
    )  # noqa: S106
    store = create_store(owner=owner, name="Listed Co", slug="list-listed-co")

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "list-owner-2@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = client.get("/api/v1/dashboard/stores")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == str(store.id)
    assert response.data[0]["name"] == "Listed Co"
    assert response.data[0]["slug"] == "list-listed-co"
    assert response.data[0]["status"] == "active"


def test_store_list_is_not_throttled_at_the_store_create_rate():
    """store_create is 10/hour -- listing must not share that budget."""
    client = _client_for("list-throttle@example.com")
    for _ in range(15):
        response = client.get("/api/v1/dashboard/stores")
        assert response.status_code == 200
