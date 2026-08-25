"""
THE test suite docs/DECISIONS.md governance point 1 requires: automated,
generic proof that

  * Store A cannot READ Store B's rows
  * Store A cannot UPDATE Store B's rows
  * Store A cannot DELETE Store B's rows
  * changing store_id in a request body cannot bypass isolation
    (modeled here as: writing a row for store B while the tenant context
    is store A)

...for every `TenantOwnedModel` subclass in the project, automatically --
not just the ones someone remembered to write a test for. Any app that
adds a new tenant-owned model and forgets to register a factory (see
apps/tenancy/testing.py) fails `test_every_tenant_owned_model_is_registered`
loudly in CI, rather than silently shipping untested.

Every assertion here goes through `.unscoped` (bypassing the Python-level
TenantManager filter) so what's actually being proven is PostgreSQL Row-
Level Security itself -- layer 4 of the defense in docs/ARCHITECTURE.md
section 2.3 -- not just the ORM convenience layer on top of it. A second,
smaller test proves the ergonomic `.objects` layer separately.
"""

from __future__ import annotations

import pytest
from django.apps import apps as django_apps
from django.db import Error as DjangoDatabaseError
from django.db import transaction
from django.utils import timezone

import apps.accounts.tests.isolation_factories  # noqa: F401 -- registers StoreMembership
import apps.carts.tests.isolation_factories  # noqa: F401 -- registers cart models
import apps.catalog.tests.isolation_factories  # noqa: F401 -- registers catalog models
import apps.inventory.tests.isolation_factories  # noqa: F401 -- registers inventory models
import apps.notifications.tests.isolation_factories  # noqa: F401 -- registers notifications models
import apps.orders.tests.isolation_factories  # noqa: F401 -- registers orders models
import apps.payments.tests.isolation_factories  # noqa: F401 -- registers payments models
import apps.pricing.tests.isolation_factories  # noqa: F401 -- registers pricing models
import apps.shipping.tests.isolation_factories  # noqa: F401 -- registers shipping models
import apps.stores.tests.isolation_factories  # noqa: F401 -- registers StoreDomain
import apps.subscriptions.tests.isolation_factories  # noqa: F401 -- registers subscriptions models
import apps.suppliers.tests.isolation_factories  # noqa: F401 -- registers suppliers models
import apps.themes.tests.isolation_factories  # noqa: F401 -- registers StoreThemeConfig
from apps.stores.models import Store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db
from apps.tenancy.models import TenantOwnedModel
from apps.tenancy.testing import all_registered

pytestmark = pytest.mark.django_db


def _discover_tenant_owned_models() -> list[type]:
    return [
        model
        for model in django_apps.get_models()
        if issubclass(model, TenantOwnedModel) and not model._meta.abstract
    ]


TENANT_OWNED_MODELS = _discover_tenant_owned_models()


def test_every_tenant_owned_model_has_a_registered_isolation_factory():
    missing = set(TENANT_OWNED_MODELS) - set(all_registered())
    assert not missing, (
        "These TenantOwnedModel subclasses have no isolation-test factory "
        f"registered (see apps/tenancy/testing.py): {missing}. Every "
        "tenant-owned model MUST be covered by this suite before it ships."
    )


def _create_store(slug: str) -> Store:
    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            return Store.objects.create(name=slug, slug=slug)
        finally:
            clear_tenant_context_from_db()


def _create_row_for(model: type, store: Store, suffix: str):
    factory = all_registered()[model].factory
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return factory(store, suffix)
        finally:
            clear_tenant_context_from_db()


@pytest.fixture
def two_stores():
    return _create_store("iso-store-a"), _create_store("iso-store-b")


@pytest.mark.parametrize("model", TENANT_OWNED_MODELS, ids=lambda m: m.__name__)
def test_store_a_cannot_read_store_bs_row_even_unscoped(model, two_stores):
    """
    For almost every model this proves RLS actually hides the row. The
    one documented exception is a model registered with
    `select_is_open=True` (currently only `StoreDomain` -- hostnames are
    public, and TenantMiddleware must resolve them before any tenant
    context exists). For those, we instead assert the row IS visible via
    `.unscoped` -- proving the *deliberate* openness holds, and proving
    `.objects` (the ergonomic layer) still hides it, which is checked
    separately by `test_default_manager_also_hides_other_stores_rows`.
    """
    store_a, store_b = two_stores
    row_b = _create_row_for(model, store_b, "read")
    spec = all_registered()[model]

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            visible = model.unscoped.filter(pk=row_b.pk).exists()
        finally:
            clear_tenant_context_from_db()

    if spec.select_is_open:
        assert visible, (
            f"{model.__name__} is registered select_is_open=True but its "
            "RLS SELECT policy is not actually open -- registration and "
            "migration have drifted apart."
        )
    else:
        assert not visible, (
            f"{model.__name__}: store A could see store B's row via "
            "PostgreSQL RLS -- isolation is broken at the DB layer."
        )


@pytest.mark.parametrize("model", TENANT_OWNED_MODELS, ids=lambda m: m.__name__)
def test_store_a_cannot_update_store_bs_row_even_unscoped(model, two_stores):
    store_a, store_b = two_stores
    row_b = _create_row_for(model, store_b, "update")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            affected = model.unscoped.filter(pk=row_b.pk).update(updated_at=timezone.now())
        finally:
            clear_tenant_context_from_db()
    assert affected == 0, (
        f"{model.__name__}: store A's UPDATE matched store B's row -- RLS "
        "did not filter it out for the UPDATE command."
    )

    # And the row is provably untouched, verified from store B's own context.
    with tenant_context(TenantContext(store_id=store_b.id)):
        apply_tenant_context_to_db(store_b.id)
        try:
            fresh = model.objects.get(pk=row_b.pk)
        finally:
            clear_tenant_context_from_db()
    assert fresh.updated_at == row_b.updated_at


@pytest.mark.parametrize("model", TENANT_OWNED_MODELS, ids=lambda m: m.__name__)
def test_store_a_cannot_delete_store_bs_row_even_unscoped(model, two_stores):
    store_a, store_b = two_stores
    row_b = _create_row_for(model, store_b, "delete")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            deleted_count, _ = model.unscoped.filter(pk=row_b.pk).delete()
        finally:
            clear_tenant_context_from_db()
    assert deleted_count == 0, (
        f"{model.__name__}: store A's DELETE removed store B's row -- RLS "
        "did not filter it out for the DELETE command."
    )

    with tenant_context(TenantContext(store_id=store_b.id)):
        apply_tenant_context_to_db(store_b.id)
        try:
            assert model.objects.filter(pk=row_b.pk).exists()
        finally:
            clear_tenant_context_from_db()


@pytest.mark.parametrize("model", TENANT_OWNED_MODELS, ids=lambda m: m.__name__)
def test_writing_a_row_for_another_store_is_rejected(model, two_stores):
    """
    Models the "attacker edits store_id in the request body/URL" scenario
    from docs/DECISIONS.md governance point 1: even if application code
    somehow ends up trying to INSERT a row stamped with store B's id while
    the active tenant context is store A, PostgreSQL's RLS `WITH CHECK`
    clause must reject it outright.
    """
    store_a, store_b = two_stores

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            with pytest.raises(DjangoDatabaseError) as exc_info:
                with transaction.atomic(using="default"):
                    all_registered()[model].factory(store_b, "cross-tenant-insert")
        finally:
            clear_tenant_context_from_db()

    # Must be a policy violation, not some unrelated failure.
    assert (
        "row-level security" in str(exc_info.value).lower()
        or "policy" in str(exc_info.value).lower()
    )


@pytest.mark.parametrize("model", TENANT_OWNED_MODELS, ids=lambda m: m.__name__)
def test_default_manager_also_hides_other_stores_rows(model, two_stores):
    """The ergonomic layer (TenantManager) agrees with RLS -- belt and
    braces, not a substitute for the `.unscoped` proofs above."""
    store_a, store_b = two_stores
    row_a = _create_row_for(model, store_a, "ergonomic-a")
    _create_row_for(model, store_b, "ergonomic-b")

    with tenant_context(TenantContext(store_id=store_a.id)):
        apply_tenant_context_to_db(store_a.id)
        try:
            pks = set(model.objects.values_list("pk", flat=True))
        finally:
            clear_tenant_context_from_db()
    assert pks == {row_a.pk}
