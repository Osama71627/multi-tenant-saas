"""`GET /api/v1/storefront/payments/providers` -- Phase 13. Only
`provider_key` for ENABLED providers, never `credentials_hint`/`mode`/
`public_metadata` (merchant-only), and never another store's providers."""

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
        email="sf-payments-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    dashboard = _login_as("sf-payments-owner@example.com")
    store = store_services.create_store(
        owner=owner, name="Storefront Payments Co", slug="sf-payments-co"
    )
    hostname = "sf-payments-co.lvh.me"

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    connect = dashboard.post(
        f"/api/v1/dashboard/stores/{store.id}/payments/providers",
        {"provider_key": "manual_cod", "mode": "test"},
        format="json",
    )
    assert connect.status_code == 201, connect.data

    return {"store": store, "storefront": HostPinnedClient()}


def test_returns_only_enabled_provider_keys(store_ctx):
    response = store_ctx["storefront"].get("/api/v1/storefront/payments/providers")
    assert response.status_code == 200
    assert response.json() == [{"provider_key": "manual_cod"}]


def test_another_stores_host_cannot_see_this_stores_providers(store_ctx):
    other_owner = PlatformUser.objects.create_user(
        email="sf-payments-owner-b@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_services.create_store(
        owner=other_owner, name="Storefront Payments Co B", slug="sf-payments-co-b"
    )

    class OtherHostClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", "sf-payments-co-b.lvh.me")
            return super().generic(method, path, *args, **kwargs)

    response = OtherHostClient().get("/api/v1/storefront/payments/providers")
    assert response.status_code == 200
    assert response.json() == []
