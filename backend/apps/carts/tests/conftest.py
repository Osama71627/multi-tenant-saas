import contextlib

import pytest
from django.test import Client

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db


@contextlib.contextmanager
def store_db_context(store):
    """See apps/catalog/tests/conftest.py -- same pattern, same reasoning."""
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            yield
        finally:
            clear_tenant_context_from_db()


def _login_as(email: str, password: str = "correct-h0rse!"):  # noqa: S107
    from rest_framework.test import APIClient

    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


@pytest.fixture
def store_with_hostname():
    """
    A real Store reachable by Host header -- the storefront surface
    (apps.carts) resolves tenants by Host, never a path segment.
    `store_services.create_store` already auto-provisions a primary
    `StoreDomain` at `f"{slug}.{PLATFORM_ROOT_DOMAIN}"` (Phase 3), so
    there's no need to create a second one here.
    """
    owner = PlatformUser.objects.create_user(
        email="cart-store-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    dashboard_client = _login_as("cart-store-owner@example.com")
    store = store_services.create_store(owner=owner, name="Cart Co", slug="cart-co")
    hostname = "cart-co.lvh.me"
    return {
        "store": store,
        "hostname": hostname,
        "owner": owner,
        "dashboard_client": dashboard_client,
    }


@pytest.fixture
def storefront_client(store_with_hostname):
    """A guest storefront `Client` pinned to `store_with_hostname`'s Host header."""
    hostname = store_with_hostname["hostname"]

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    return HostPinnedClient()


@pytest.fixture
def variant_in_store(store_with_hostname):
    """A real, active, priced ProductVariant in `store_with_hostname`, via the dashboard API."""
    ctx = store_with_hostname
    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products",
        {"name": "Widget", "slug": "widget", "sku": "WIDGET-001", "price_amount": 2000},
        format="json",
    )
    variant = response.data["variants"][0]
    # Products default to draft -- a cart can't sell a draft product.
    product_id = response.data["id"]
    ctx["dashboard_client"].patch(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products/{product_id}",
        {"status": "active"},
        format="json",
    )
    return {**ctx, "variant_id": variant["id"], "product_id": product_id, "price_amount": 2000}
