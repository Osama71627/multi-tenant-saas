"""`GET /api/v1/storefront/inventory/availability` -- Phase 13. Only a
summed available-across-locations integer per variant id, never a
per-location breakdown or any other `StockBalance` field."""

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
        email="sf-inventory-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    dashboard = _login_as("sf-inventory-owner@example.com")
    store = store_services.create_store(
        owner=owner, name="Storefront Inventory Co", slug="sf-inv-co"
    )
    hostname = "sf-inv-co.lvh.me"

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    product = dashboard.post(
        f"/api/v1/dashboard/stores/{store.id}/products",
        {"name": "Widget", "slug": "widget", "sku": "WIDGET-1", "price_amount": 1000},
        format="json",
    )
    variant_id = product.data["variants"][0]["id"]

    location = dashboard.post(
        f"/api/v1/dashboard/stores/{store.id}/inventory/locations",
        {"name": "Main"},
        format="json",
    )
    dashboard.post(
        f"/api/v1/dashboard/stores/{store.id}/inventory/adjust",
        {
            "variant": variant_id,
            "location": location.data["id"],
            "delta": 15,
            "reason": "initial",
        },
        format="json",
    )

    return {"store": store, "storefront": HostPinnedClient(), "variant_id": variant_id}


def test_returns_summed_available_quantity(store_ctx):
    response = store_ctx["storefront"].get(
        f"/api/v1/storefront/inventory/availability?variant={store_ctx['variant_id']}"
    )
    assert response.status_code == 200
    assert response.json() == {store_ctx["variant_id"]: 15}


def test_variant_with_no_stock_rows_is_absent(store_ctx):
    import uuid

    response = store_ctx["storefront"].get(
        f"/api/v1/storefront/inventory/availability?variant={uuid.uuid4()}"
    )
    assert response.status_code == 200
    assert response.json() == {}


def test_no_variant_param_returns_empty_object(store_ctx):
    response = store_ctx["storefront"].get("/api/v1/storefront/inventory/availability")
    assert response.status_code == 200
    assert response.json() == {}


def test_another_stores_host_cannot_see_this_variants_stock(store_ctx):
    """RLS boundary, not just a query filter: querying Store A's real
    variant id through Store B's Host must come back empty, never A's
    real quantity -- `StockBalance.objects` is tenant-scoped by the GUC
    TenantMiddleware sets from B's Host, so A's rows are invisible from
    this connection regardless of which id is asked for."""
    other_owner = PlatformUser.objects.create_user(
        email="sf-inventory-owner-b@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_services.create_store(
        owner=other_owner, name="Storefront Inventory Co B", slug="sf-inv-co-b"
    )

    class OtherHostClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", "sf-inv-co-b.lvh.me")
            return super().generic(method, path, *args, **kwargs)

    response = OtherHostClient().get(
        f"/api/v1/storefront/inventory/availability?variant={store_ctx['variant_id']}"
    )
    assert response.status_code == 200
    assert response.json() == {}
