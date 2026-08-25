"""
Security-focused coverage for `POST /api/v1/dashboard/stores` per the
explicit Phase 3 requirements: who can create a store, ownership,
StoreMembership creation, duplicate slugs, and transaction boundaries.
Runs against real PostgreSQL 18.6 (RLS/uniqueness enforced by the DB
itself, not simulated).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser, StoreMembership
from apps.stores.models import Store, StoreDomain
from apps.stores.services import RESERVED_SLUGS
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(email="merchant@example.com", password="correct-h0rse!")


@pytest.fixture
def client(user):
    api_client = APIClient()
    login = api_client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return api_client


def _counts_within(store) -> tuple[int, int]:
    """
    (StoreDomain count, StoreMembership count) for `store`, queried with
    the tenant context genuinely set to it. Deliberately NOT a global
    `.unscoped` count with no context: `.unscoped` only skips the
    Python-side filter, not RLS itself (apps/tenancy/models.py) -- with
    no tenant context active, a restrictively-RLS'd table (unlike
    `Store`, which has an intentionally open SELECT policy) correctly
    returns zero rows for `app_user` no matter which manager is used.
    """
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return (
                StoreDomain.objects.filter(store=store).count(),
                StoreMembership.objects.filter(store=store).count(),
            )
        finally:
            clear_tenant_context_from_db()


def test_unauthenticated_request_cannot_create_a_store():
    response = APIClient().post(
        "/api/v1/dashboard/stores", {"name": "Acme", "slug": "acme"}, format="json"
    )
    assert response.status_code == 401
    assert not Store.objects.filter(slug="acme").exists()


def test_authenticated_user_can_create_a_store(client, user):
    response = client.post(
        "/api/v1/dashboard/stores", {"name": "Acme Store", "slug": "acme-store"}, format="json"
    )
    assert response.status_code == 201, response.data
    assert response.data["name"] == "Acme Store"
    assert response.data["slug"] == "acme-store"
    assert response.data["status"] == "active"


def test_email_verification_is_not_required_to_create_a_store(client, user):
    """Documented scope decision -- see apps/stores/services.py:create_store."""
    assert user.email_verified_at is None
    response = client.post(
        "/api/v1/dashboard/stores",
        {"name": "Unverified Co", "slug": "unverified-co"},
        format="json",
    )
    assert response.status_code == 201


def test_creating_a_store_provisions_exactly_one_primary_subdomain(client):
    response = client.post(
        "/api/v1/dashboard/stores", {"name": "Domain Co", "slug": "domain-co"}, format="json"
    )
    store_id = response.data["id"]

    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            store = Store.objects.get(id=store_id)
        finally:
            clear_tenant_context_from_db()

    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            rows = list(StoreDomain.unscoped.filter(store=store))
        finally:
            clear_tenant_context_from_db()

    assert len(rows) == 1
    assert rows[0].is_primary is True
    assert rows[0].kind == StoreDomain.Kind.SUBDOMAIN
    assert rows[0].hostname == "domain-co.lvh.me"


def test_creating_a_store_makes_the_creator_the_active_owner(client, user):
    response = client.post(
        "/api/v1/dashboard/stores", {"name": "Owner Co", "slug": "owner-co"}, format="json"
    )
    store_id = response.data["id"]

    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            store = Store.objects.get(id=store_id)
        finally:
            clear_tenant_context_from_db()

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            membership = StoreMembership.objects.get(user=user)
        finally:
            clear_tenant_context_from_db()

    assert membership.role == StoreMembership.Role.OWNER
    assert membership.status == StoreMembership.Status.ACTIVE


def test_two_stores_by_the_same_user_get_two_independent_owner_memberships(client, user):
    r1 = client.post(
        "/api/v1/dashboard/stores", {"name": "One", "slug": "store-one"}, format="json"
    )
    r2 = client.post(
        "/api/v1/dashboard/stores", {"name": "Two", "slug": "store-two"}, format="json"
    )
    assert r1.status_code == r2.status_code == 201
    assert r1.data["id"] != r2.data["id"]

    for response in (r1, r2):
        with tenant_context(TenantContext(store_id=response.data["id"])):
            apply_tenant_context_to_db(response.data["id"])
            try:
                membership = StoreMembership.objects.get(user=user)
            finally:
                clear_tenant_context_from_db()
        assert membership.role == StoreMembership.Role.OWNER
        assert str(membership.store_id) == response.data["id"]


def test_duplicate_slug_is_rejected_cleanly(client):
    first = client.post(
        "/api/v1/dashboard/stores", {"name": "First", "slug": "taken-slug"}, format="json"
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/dashboard/stores", {"name": "Second", "slug": "taken-slug"}, format="json"
    )
    assert second.status_code == 400
    assert Store.objects.filter(slug="taken-slug").count() == 1


def test_duplicate_slug_check_is_case_insensitive(client):
    client.post("/api/v1/dashboard/stores", {"name": "First", "slug": "MixedCase"}, format="json")
    response = client.post(
        "/api/v1/dashboard/stores", {"name": "Second", "slug": "mixedcase"}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.parametrize("slug", sorted(RESERVED_SLUGS)[:5])
def test_reserved_slugs_are_rejected(client, slug):
    response = client.post(
        "/api/v1/dashboard/stores", {"name": "Nope", "slug": slug}, format="json"
    )
    assert response.status_code == 400
    assert not Store.objects.filter(slug=slug).exists()


def test_invalid_slug_format_is_rejected(client):
    response = client.post(
        "/api/v1/dashboard/stores",
        {"name": "Bad Slug", "slug": "not a valid slug!!"},
        format="json",
    )
    assert response.status_code == 400


def test_failed_creation_leaves_no_orphaned_rows(client):
    """
    Proves the whole create_store() transaction is atomic: a rejected
    duplicate-slug attempt must not leave behind a Store, StoreDomain, or
    StoreMembership row for the failed attempt.
    """
    first = client.post(
        "/api/v1/dashboard/stores", {"name": "First", "slug": "atomic-slug"}, format="json"
    )
    store = Store.objects.get(id=first.data["id"])  # open SELECT policy, no context needed
    before_stores = Store.objects.filter(slug="atomic-slug").count()
    before_domains, before_memberships = _counts_within(store)

    response = client.post(
        "/api/v1/dashboard/stores", {"name": "Duplicate", "slug": "atomic-slug"}, format="json"
    )
    assert response.status_code == 400

    after_domains, after_memberships = _counts_within(store)
    assert Store.objects.filter(slug="atomic-slug").count() == before_stores == 1
    assert after_domains == before_domains == 1
    assert after_memberships == before_memberships == 1


def test_client_cannot_supply_a_store_id_to_hijack_an_existing_store(client, user):
    """
    Store.id is server-generated (uuid7 default, not client-writable via
    the serializer -- CreateStoreSerializer only accepts name/slug). This
    documents that guarantee explicitly rather than leaving it implicit.
    """
    existing = client.post(
        "/api/v1/dashboard/stores", {"name": "Existing", "slug": "existing-store"}, format="json"
    )
    other_user = PlatformUser.objects.create_user(
        email="attacker@example.com", password="x1234567!"
    )
    other_client = APIClient()
    login = other_client.post(
        "/api/v1/auth/login", {"email": other_user.email, "password": "x1234567!"}, format="json"
    )
    other_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    hijack_attempt = other_client.post(
        "/api/v1/dashboard/stores",
        {
            "name": "Hijack",
            "slug": "hijack-slug",
            "id": existing.data["id"],
            "store": existing.data["id"],
        },
        format="json",
    )
    assert hijack_attempt.status_code == 201
    assert hijack_attempt.data["id"] != existing.data["id"]  # a NEW store was made, not a hijack


def test_store_creation_is_rate_limited(client):
    """DEFAULT_THROTTLE_RATES['store_create'] = '10/hour' (config/settings/base.py)."""
    for i in range(10):
        response = client.post(
            "/api/v1/dashboard/stores",
            {"name": f"Rate {i}", "slug": f"rate-slug-{i}"},
            format="json",
        )
        assert response.status_code == 201, f"attempt {i} unexpectedly failed: {response.data}"

    eleventh = client.post(
        "/api/v1/dashboard/stores", {"name": "One Too Many", "slug": "rate-slug-11"}, format="json"
    )
    assert eleventh.status_code == 429
