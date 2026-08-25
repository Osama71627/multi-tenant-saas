import contextlib

import pytest
from django.test import Client
from rest_framework.test import APIClient

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
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


def make_client_for(email: str, password: str = "correct-h0rse!"):  # noqa: S107
    user = PlatformUser.objects.create_user(email=email, password=password)
    return _login_as(email, password), user


@pytest.fixture
def store_with_hostname():
    """See apps/carts/tests/conftest.py -- same pattern. `create_store` auto-provisions
    a primary `StoreDomain` at `f"{slug}.{PLATFORM_ROOT_DOMAIN}"` (Phase 3)."""
    owner = PlatformUser.objects.create_user(
        email="order-store-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    dashboard_client = _login_as("order-store-owner@example.com")
    store = store_services.create_store(owner=owner, name="Order Co", slug="order-co")
    hostname = "order-co.lvh.me"
    return {
        "store": store,
        "hostname": hostname,
        "owner": owner,
        "dashboard_client": dashboard_client,
    }


@pytest.fixture
def storefront_client(store_with_hostname):
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
    product_id = response.data["id"]
    ctx["dashboard_client"].patch(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products/{product_id}",
        {"status": "active"},
        format="json",
    )
    return {**ctx, "variant_id": variant["id"], "product_id": product_id, "price_amount": 2000}


def setup_flat_shipping(ctx, *, price_amount: int = 1500) -> dict:
    """Zone(SA) + flat method + rate, via the real dashboard shipping API (apps.shipping,
    Phase 7) -- returns the method id so a test can drive `checkout/shipping` with it."""
    store_id = ctx["store"].id
    zone = (
        ctx["dashboard_client"]
        .post(
            f"/api/v1/dashboard/stores/{store_id}/shipping/zones",
            {"name": "KSA", "countries": ["SA"]},
            format="json",
        )
        .data
    )
    method = (
        ctx["dashboard_client"]
        .post(
            f"/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone['id']}/methods",
            {"zone": zone["id"], "name": "Standard", "kind": "flat"},
            format="json",
        )
        .data
    )
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{store_id}/shipping/methods/{method['id']}/rates",
        {"method": method["id"], "price_amount": price_amount, "currency": "SAR"},
        format="json",
    )
    return method


VALID_ADDRESS = {
    "recipient_name": "Test Shopper",
    "phone": "+966500000000",
    "country_code": "SA",
    "region": "Riyadh",
    "city": "Riyadh",
    "postal_code": "11564",
    "line1": "123 Test Street",
}


def add_stock(store, variant_id: str, *, quantity: int = 10):
    """Every variant needs a real `StockLocation` + `StockBalance` before it can be
    checked out -- apps.inventory (Phase 5) has no "untracked/digital" opt-out."""
    from apps.catalog.models import ProductVariant
    from apps.inventory import services as inventory_services

    with store_db_context(store):
        location = inventory_services.create_location(store=store, name="Main Warehouse")
        variant = ProductVariant.objects.get(id=variant_id)
        inventory_services.adjust_stock(
            store=store, variant=variant, location=location, delta=quantity, reason="initial stock"
        )
        return location


def add_item_and_start_checkout(storefront_client, variant_id: str) -> dict:
    """Adds one unit of `variant_id` to the storefront cart and starts checkout.
    Returns the checkout session dict (includes `id`)."""
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": variant_id, "quantity": 1},
        content_type="application/json",
    )
    response = storefront_client.post("/api/v1/storefront/checkout/start")
    assert response.status_code == 201, response.data
    return response.data


def complete_address_and_shipping(storefront_client, method_id: str) -> dict:
    storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": "shopper@example.com", "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": method_id},
        content_type="application/json",
    )
    assert response.status_code == 200, response.data
    return response.data
