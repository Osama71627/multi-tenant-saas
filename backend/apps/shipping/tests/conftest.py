import contextlib

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db


@contextlib.contextmanager
def store_db_context(store):
    """See apps/catalog/tests/conftest.py -- same documented pattern (docs/PHASE_3_REPORT.md)."""
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            yield
        finally:
            clear_tenant_context_from_db()


def make_client_for(
    email: str, password: str = "correct-h0rse!"  # noqa: S107
) -> tuple[APIClient, PlatformUser]:
    user = PlatformUser.objects.create_user(email=email, password=password)
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client, user


@pytest.fixture
def owner_client_and_store():
    client, owner = make_client_for("shipping-owner@example.com")
    store = store_services.create_store(owner=owner, name="Shipping Co", slug="shipping-co")
    return client, owner, store
