"""
`Store` (the tenant root) is deliberately NOT a `TenantOwnedModel` -- it
doesn't have a `store_id`, it IS the store -- so it's outside the generic
parametrized suite in backend/tests/test_tenant_isolation.py and needs
its own tests for its hand-written RLS policies (see
apps/stores/migrations/0001_initial.py): open SELECT/INSERT, but
UPDATE/DELETE restricted to the store's own context.
"""

import pytest
from django.db import transaction

from apps.stores.models import Store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


def _make_store(slug: str) -> Store:
    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            return Store.objects.create(name=slug, slug=slug)
        finally:
            clear_tenant_context_from_db()


def test_store_select_is_open_across_tenants():
    store_a = _make_store("rls-store-select-a")
    store_b = _make_store("rls-store-select-b")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            assert Store.objects.filter(pk=store_b.pk).exists(), (
                "Store SELECT should be open -- a store's name/slug/status "
                "is comparable to public DNS-level information."
            )
        finally:
            clear_tenant_context_from_db()


def test_store_cannot_update_a_different_stores_row():
    store_a = _make_store("rls-store-update-a")
    store_b = _make_store("rls-store-update-b")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            affected = Store.objects.filter(pk=store_b.pk).update(name="hijacked")
        finally:
            clear_tenant_context_from_db()
    assert affected == 0

    store_b.refresh_from_db()
    assert store_b.name == "rls-store-update-b"


def test_store_cannot_delete_a_different_stores_row():
    store_a = _make_store("rls-store-delete-a")
    store_b = _make_store("rls-store-delete-b")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            deleted_count, _ = Store.objects.filter(pk=store_b.pk).delete()
        finally:
            clear_tenant_context_from_db()
    assert deleted_count == 0
    assert Store.objects.filter(pk=store_b.pk).exists()


def test_store_can_update_its_own_row():
    store_a = _make_store("rls-store-update-self")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            affected = Store.objects.filter(pk=store_a.pk).update(name="renamed")
        finally:
            clear_tenant_context_from_db()
    assert affected == 1
    store_a.refresh_from_db()
    assert store_a.name == "renamed"


def test_store_insert_is_open_with_no_tenant_context():
    """
    Registering a brand-new store must be possible before any tenant
    context exists -- that's the entire point of registration.
    """
    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            with transaction.atomic(using="default"):
                store = Store.objects.create(name="brand-new", slug="brand-new-store")
        finally:
            clear_tenant_context_from_db()
    assert store.pk is not None
