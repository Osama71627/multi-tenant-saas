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
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

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


def test_a_store_with_no_logo_lists_a_null_logo_not_a_broken_url():
    owner = PlatformUser.objects.create_user(
        email="list-no-logo@example.com", password="correct-h0rse!"  # noqa: S106
    )
    create_store(owner=owner, name="No Logo Co", slug="list-no-logo-co")

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "list-no-logo@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = client.get("/api/v1/dashboard/stores")
    assert response.status_code == 200
    assert response.data[0]["logo"] is None


def test_a_store_with_a_logo_lists_a_real_absolute_url():
    """Real gap found live: Store.logo (Phase F's business-info upload)
    saved to disk correctly but was never returned by ANY serializer --
    structurally unviewable by any client. Proven fixed here: the list
    endpoint's own `logo` field must be a real, absolute, loadable URL,
    not a bare relative MEDIA_URL path (the dashboard is a different
    origin from Django entirely -- a relative path would 404 there)."""
    owner = PlatformUser.objects.create_user(
        email="list-with-logo@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store = create_store(owner=owner, name="Logo Co", slug="list-logo-co")
    # UPDATE on Store is RLS-restricted to the store's own context -- see
    # apps/stores/tests/test_store_settings.py's identical comment.
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            store.logo = "store_logos/test-logo.png"
            store.save(update_fields=["logo"])
        finally:
            clear_tenant_context_from_db()

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "list-with-logo@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = client.get("/api/v1/dashboard/stores")
    assert response.status_code == 200
    logo_url = response.data[0]["logo"]
    assert logo_url is not None
    assert logo_url.startswith("http")
    assert "store_logos/test-logo.png" in logo_url
