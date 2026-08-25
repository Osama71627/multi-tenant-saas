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
    owner = PlatformUser.objects.create_user(
        email="payment-store-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    dashboard_client = _login_as("payment-store-owner@example.com")
    store = store_services.create_store(owner=owner, name="Payment Co", slug="payment-co")
    hostname = "payment-co.lvh.me"
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


def add_stock(store, variant_id: str, *, quantity: int = 10):
    from apps.catalog.models import ProductVariant
    from apps.inventory import services as inventory_services
    from apps.inventory.models import StockLocation

    with store_db_context(store):
        # `create_location` has no get-or-create semantics (Phase 5: a location is
        # always an explicit, deliberate act) -- reuse it here so a test calling
        # `create_order`/`add_stock` more than once for the same store doesn't hit
        # `uniq_location_name_per_store`.
        location = StockLocation.objects.filter(name="Main Warehouse").first()
        if location is None:
            location = inventory_services.create_location(store=store, name="Main Warehouse")
        variant = ProductVariant.objects.get(id=variant_id)
        inventory_services.adjust_stock(
            store=store, variant=variant, location=location, delta=quantity, reason="initial stock"
        )
        return location


def setup_flat_shipping(ctx, *, price_amount: int = 1500) -> dict:
    """Reuses an existing zone/method if this store already has one -- a test calling
    `create_order` more than once for the same store must not end up with two
    same-priority zones racing `find_matching_zone`'s tie-break (whichever zone was
    created FIRST always wins, silently orphaning any method_id from a later call)."""
    store_id = ctx["store"].id
    existing = (
        ctx["dashboard_client"].get(f"/api/v1/dashboard/stores/{store_id}/shipping/zones").data
    )
    if existing:
        zone = existing[0]
        methods = (
            ctx["dashboard_client"]
            .get(f"/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone['id']}/methods")
            .data
        )
        if methods:
            return methods[0]
    else:
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


def enable_provider(
    ctx, *, provider_key: str, credentials: str = "", webhook_secret: str = ""
) -> dict:
    """Creates a `StoreProviderConfig` via the real dashboard API (write-only
    secrets -- never round-tripped back in the response)."""
    payload = {"provider_key": provider_key, "mode": "test", "is_enabled": True}
    if credentials:
        payload["credentials"] = credentials
    if webhook_secret:
        payload["webhook_secret"] = webhook_secret
    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers", payload, format="json"
    )
    assert response.status_code == 201, response.data
    return response.data


def create_order(ctx, storefront_client, *, quantity: int = 1) -> dict:
    """Drives the real Phase 8 checkout flow end to end -- returns the created Order dict."""
    add_stock(ctx["store"], ctx["variant_id"], quantity=quantity + 5)
    method = setup_flat_shipping(ctx)

    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": quantity},
        content_type="application/json",
    )
    storefront_client.post("/api/v1/storefront/checkout/start")
    storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": "shopper@example.com", "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": method["id"]},
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=f"order-key-{ctx['store'].id}-{quantity}",
    )
    assert response.status_code == 201, response.data
    return response.data
