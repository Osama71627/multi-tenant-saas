"""`GET /api/v1/storefront/context` -- Phase 13. Must return the
public-safe store identity + the store's pinned theme/settings, and
never merchant-only fields (`contact_email`/`contact_phone`)."""

from __future__ import annotations

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


def _login_as(email: str, password: str = "correct-h0rse!") -> APIClient:  # noqa: S107
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


@pytest.fixture
def store_ctx():
    owner = PlatformUser.objects.create_user(
        email="sf-theme-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store = store_services.create_store(owner=owner, name="Storefront Theme Co", slug="sf-theme-co")
    hostname = "sf-theme-co.lvh.me"

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    return {"store": store, "storefront": HostPinnedClient()}


def test_context_returns_store_and_theme(store_ctx):
    response = store_ctx["storefront"].get("/api/v1/storefront/context")
    assert response.status_code == 200
    body = response.json()

    assert body["store"]["name"] == "Storefront Theme Co"
    assert body["store"]["default_currency"] == "SAR"
    assert body["theme"]["theme_code"] == "aurora"
    assert body["theme"]["theme_version_number"] == 1
    assert "primary_color" in body["theme"]["settings"]


def test_context_returns_a_null_logo_when_none_is_set(store_ctx):
    response = store_ctx["storefront"].get("/api/v1/storefront/context")
    assert response.json()["store"]["logo"] is None


def test_context_returns_a_relative_logo_url_when_one_is_set(store_ctx):
    """Real gap found live, in two layers. First: every storefront
    theme's header/footer only ever had the store NAME to render
    (plain text wordmark) -- `logo` was never returned by this endpoint
    at all, the same underlying serializer gap already fixed for the
    dashboard's own StoreListItemSerializer/StoreDetailSerializer.
    Second, found fixing the first: `request.build_absolute_uri()`
    (that fix's first attempt) reads the SAME `X-Forwarded-Host` header
    tenant resolution needs -- in local dev, where the storefront (Next,
    port 4000) and Django (port 8000) are genuinely different ports
    behind the SAME tenant hostname, that produced a URL pointing at
    the storefront's own port instead of Django's. Deliberately
    relative here instead (apps.themes.serializers.
    StorefrontStoreSerializer.get_logo's own docstring has the full
    story) -- frontend/apps/storefront/lib/theme.ts's
    `getStorefrontContext()` applies the SAME origin-construction
    `lib/backend.ts`'s `browserBackendOrigin()` already uses for every
    other storefront API call."""
    from apps.tenancy.context import TenantContext, tenant_context
    from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

    store = store_ctx["store"]
    # UPDATE on Store is RLS-restricted to the store's own context -- see
    # apps/stores/tests/test_store_settings.py's identical comment.
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            store.logo = "store_logos/storefront-test-logo.png"
            store.save(update_fields=["logo"])
        finally:
            clear_tenant_context_from_db()

    response = store_ctx["storefront"].get("/api/v1/storefront/context")
    logo_url = response.json()["store"]["logo"]
    assert logo_url == "/media/store_logos/storefront-test-logo.png"


def test_context_never_exposes_contact_fields(store_ctx):
    response = store_ctx["storefront"].get("/api/v1/storefront/context")
    assert "contact_email" not in response.json()["store"]
    assert "contact_phone" not in response.json()["store"]


def test_unknown_host_404s():
    response = Client().get("/api/v1/storefront/context", HTTP_HOST="nonexistent-store.lvh.me")
    assert response.status_code == 404


def test_two_stores_hosts_never_cross_over(store_ctx):
    """The real HTTP tenant boundary: Store A's Host must return ONLY
    Store A's context, never Store B's, and vice versa -- Host-header
    resolution (apps/stores/middleware.py), not RLS alone, is what's
    under test here."""
    other_owner = PlatformUser.objects.create_user(
        email="sf-theme-owner-b@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_services.create_store(
        owner=other_owner, name="Storefront Theme Co B", slug="sf-theme-co-b"
    )

    class OtherHostClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", "sf-theme-co-b.lvh.me")
            return super().generic(method, path, *args, **kwargs)

    response_a = store_ctx["storefront"].get("/api/v1/storefront/context")
    response_b = OtherHostClient().get("/api/v1/storefront/context")

    assert response_a.json()["store"]["name"] == "Storefront Theme Co"
    assert response_b.json()["store"]["name"] == "Storefront Theme Co B"
