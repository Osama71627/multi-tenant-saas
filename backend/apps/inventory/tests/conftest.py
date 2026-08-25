import contextlib

import pytest
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


def login_as(email: str, password: str = "correct-h0rse!") -> APIClient:  # noqa: S107
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


def make_client_for(
    email: str, password: str = "correct-h0rse!"  # noqa: S107
) -> tuple[APIClient, PlatformUser]:
    user = PlatformUser.objects.create_user(email=email, password=password)
    return login_as(email, password), user


@pytest.fixture
def owner_client_and_store():
    client, owner = make_client_for("inventory-owner@example.com")
    store = store_services.create_store(owner=owner, name="Inventory Co", slug="inventory-co")
    return client, owner, store


@pytest.fixture
def variant_and_location(owner_client_and_store):
    """A real Product (with its default variant) and StockLocation, via the real HTTP APIs."""
    client, _owner, store = owner_client_and_store
    product = client.post(
        f"/api/v1/dashboard/stores/{store.id}/products",
        {"name": "Widget", "slug": "widget", "sku": "WIDGET-001", "price_amount": 1000},
        format="json",
    ).data
    location = client.post(
        f"/api/v1/dashboard/stores/{store.id}/inventory/locations",
        {"name": "Main Warehouse"},
        format="json",
    ).data
    return {
        "client": client,
        "store": store,
        "variant_id": product["variants"][0]["id"],
        "location_id": location["id"],
    }
