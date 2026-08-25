import contextlib

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db


@contextlib.contextmanager
def store_db_context(store):
    """
    `TenantManager` (`.objects`) requires an active tenant context, which
    HTTP requests get for free from `TenantMiddleware` but direct
    test-code ORM calls do not -- use this whenever a test wants to
    inspect a store's rows directly after making HTTP requests as that
    store's client. See docs/PHASE_3_REPORT.md for why this is a real,
    documented pattern (not a workaround) throughout this project's tests.
    """
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            yield
        finally:
            clear_tenant_context_from_db()


def login_as(email: str, password: str = "correct-h0rse!") -> APIClient:  # noqa: S107
    """Logs in as an ALREADY-EXISTING user -- e.g. a second independent client for one account."""
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
    client, owner = make_client_for("catalog-owner@example.com")
    store = store_services.create_store(owner=owner, name="Catalog Co", slug="catalog-co")
    return client, owner, store
