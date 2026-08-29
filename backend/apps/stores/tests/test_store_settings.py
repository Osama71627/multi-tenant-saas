"""
`PATCH /api/v1/dashboard/stores/<id>` -- store settings (Phase 12).
Narrow surface: name/slug/default_currency/contact_email/contact_phone
only. `status` is excluded on purpose (subscription-lifecycle-managed,
see apps.subscriptions.tasks) -- proven here by asserting a PATCH
carrying a `status` value is silently ignored, not applied.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services
from apps.stores.models import Store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


def _make_client_for(
    email: str, password: str = "correct-h0rse!"  # noqa: S107 -- test fixture, not a secret
) -> tuple[APIClient, PlatformUser]:
    user = PlatformUser.objects.create_user(email=email, password=password)
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client, user


@pytest.fixture
def owner_client_and_store():
    client, owner = _make_client_for("settings-owner@example.com")
    store = services.create_store(owner=owner, name="Settings Co", slug="settings-co")
    return client, owner, store


def test_owner_can_update_name_and_contact_fields(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}",
        {
            "name": "Settings Co Renamed",
            "contact_email": "hello@settings.co",
            "contact_phone": "+966500000000",
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["name"] == "Settings Co Renamed"
    assert response.data["contact_email"] == "hello@settings.co"
    assert response.data["contact_phone"] == "+966500000000"

    store.refresh_from_db()
    assert store.name == "Settings Co Renamed"
    assert store.contact_email == "hello@settings.co"


def test_owner_can_change_slug_to_an_available_one(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"slug": "settings-co-new"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["slug"] == "settings-co-new"


def test_patching_slug_to_itself_is_a_no_op_success(owner_client_and_store):
    """The self-exclusion in `UpdateStoreSerializer.validate_slug` must
    not reject a PATCH that doesn't change the slug at all."""
    client, _owner, store = owner_client_and_store
    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"slug": store.slug}, format="json"
    )
    assert response.status_code == 200, response.data


def test_slug_cannot_be_changed_to_a_reserved_word(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"slug": "admin"}, format="json"
    )
    assert response.status_code == 400, response.data


def test_slug_cannot_collide_with_another_stores_slug(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    _other_client, other_owner = _make_client_for("other-settings-owner@example.com")
    services.create_store(owner=other_owner, name="Other Co", slug="other-settings-co")

    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"slug": "other-settings-co"}, format="json"
    )
    assert response.status_code == 400, response.data


def test_default_currency_is_normalized_to_uppercase(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"default_currency": "usd"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["default_currency"] == "USD"


def test_status_field_in_request_body_is_ignored(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"status": "suspended"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] == Store.Status.ACTIVE

    store.refresh_from_db()
    assert store.status == Store.Status.ACTIVE


def test_non_member_cannot_update_someone_elses_store(owner_client_and_store):
    _owner_client, _owner, store = owner_client_and_store
    outsider_client, _outsider = _make_client_for("settings-outsider@example.com")

    response = outsider_client.patch(
        f"/api/v1/dashboard/stores/{store.id}", {"name": "Hijacked"}, format="json"
    )
    assert response.status_code == 403

    store.refresh_from_db()
    assert store.name == "Settings Co"


def test_get_returns_a_real_absolute_logo_url_when_one_is_set(owner_client_and_store):
    """Real gap found live: Store.logo (Phase F's business-info upload)
    saved to disk correctly but was never returned by this (or any)
    serializer -- the settings page had no way to show it back, so a
    merchant could never confirm their upload actually became their
    store's logo. Proven fixed here on the detail endpoint too (the
    list endpoint's own version of this is test_store_list.py's)."""
    client, _owner, store = owner_client_and_store
    # UPDATE on Store is RLS-restricted to the store's own context (its
    # docstring: "UPDATE/DELETE are restricted to the store's own
    # context") -- a plain `.save()` with no GUC set updates zero rows
    # and Django's own update_fields check raises DatabaseError for it.
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            store.logo = "store_logos/settings-test-logo.png"
            store.save(update_fields=["logo"])
        finally:
            clear_tenant_context_from_db()

    response = client.get(f"/api/v1/dashboard/stores/{store.id}")
    assert response.status_code == 200
    assert response.data["logo"].startswith("http")
    assert "store_logos/settings-test-logo.png" in response.data["logo"]


def test_get_returns_a_null_logo_when_none_is_set(owner_client_and_store):
    client, _owner, _store = owner_client_and_store
    response = client.get(f"/api/v1/dashboard/stores/{_store.id}")
    assert response.status_code == 200
    assert response.data["logo"] is None
