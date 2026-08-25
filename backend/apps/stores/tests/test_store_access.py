"""
Security-focused coverage for `GET /api/v1/dashboard/stores/<id>`:
membership-gated access, cross-store isolation, and that path-based
tenant resolution (not the Host header) is what actually governs this
surface -- required explicitly for Phase 3. Runs against real
PostgreSQL 18.6.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser, StoreMembership
from apps.stores import services
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
    client, owner = _make_client_for("owner@example.com")
    store = services.create_store(owner=owner, name="Access Co", slug="access-co")
    return client, owner, store


def test_owner_can_view_their_own_store(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    response = client.get(f"/api/v1/dashboard/stores/{store.id}")
    assert response.status_code == 200
    assert response.data["id"] == str(store.id)
    assert response.data["slug"] == "access-co"


def test_unauthenticated_request_is_rejected(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    response = APIClient().get(f"/api/v1/dashboard/stores/{store.id}")
    assert response.status_code == 401


def test_nonexistent_store_returns_404(owner_client_and_store):
    client, _owner, _store = owner_client_and_store
    response = client.get(f"/api/v1/dashboard/stores/{uuid.uuid4()}")
    assert response.status_code == 404


def test_non_member_cannot_view_someone_elses_store(owner_client_and_store):
    _owner_client, _owner, store = owner_client_and_store
    outsider_client, _outsider = _make_client_for("outsider@example.com")

    response = outsider_client.get(f"/api/v1/dashboard/stores/{store.id}")
    assert response.status_code == 403


def test_owner_of_store_a_cannot_view_store_b(owner_client_and_store):
    client_a, _owner_a, store_a = owner_client_and_store
    _client_b, owner_b = _make_client_for("owner-b@example.com")
    store_b = services.create_store(owner=owner_b, name="Store B", slug="store-b-access")

    response = client_a.get(f"/api/v1/dashboard/stores/{store_b.id}")
    assert response.status_code == 403

    # And the reverse holds too.
    login_b = APIClient()
    token_b = login_b.post(
        "/api/v1/auth/login",
        {"email": "owner-b@example.com", "password": "correct-h0rse!"},
        format="json",
    ).data["access"]
    login_b.credentials(HTTP_AUTHORIZATION=f"Bearer {token_b}")
    response_b = login_b.get(f"/api/v1/dashboard/stores/{store_a.id}")
    assert response_b.status_code == 403


def test_removed_membership_loses_access(owner_client_and_store):
    client, owner, store = owner_client_and_store

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            StoreMembership.objects.filter(user=owner).update(status=StoreMembership.Status.REMOVED)
        finally:
            clear_tenant_context_from_db()

    response = client.get(f"/api/v1/dashboard/stores/{store.id}")
    assert response.status_code == 403


def test_path_based_resolution_ignores_a_mismatched_host_header(owner_client_and_store):
    """
    The dashboard surface resolves the tenant from the URL path, not the
    Host header (docs/ARCHITECTURE.md section 5.1) -- a request correctly
    authorized by path must succeed even with an unrelated/attacker-
    controlled Host header.
    """
    client, _owner, store = owner_client_and_store
    response = client.get(
        f"/api/v1/dashboard/stores/{store.id}", HTTP_HOST="totally-unrelated.lvh.me"
    )
    assert response.status_code == 200
    assert response.data["id"] == str(store.id)
