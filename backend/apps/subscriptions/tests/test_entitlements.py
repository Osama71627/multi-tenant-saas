"""Unit coverage for apps.subscriptions.entitlements -- require_feature/check_quota."""

from __future__ import annotations

import pytest
from django.db import transaction

from apps.subscriptions import entitlements
from apps.subscriptions.tests.conftest import (
    create_bare_store,
    set_subscription_feature,
    set_subscription_quota,
)
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

# `databases=["default", "migrator"]`: `set_subscription_quota`/
# `set_subscription_feature` (conftest.py) write PlanVersion/Feature/Quota
# rows via the "migrator" alias, since app_user has no write policy on
# those tables at all (approved architecture decision 1) -- the same
# reason every other test in this project that needs privileged fixture
# setup goes around app_user.
pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


@pytest.fixture
def store():
    return create_bare_store("ent-store")


def _in_context(store, fn):
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return fn()
        finally:
            clear_tenant_context_from_db()


# -- check_quota (Category B path -- self-contained UsageRecord counter) ------


def test_check_quota_allows_under_limit(store):
    set_subscription_quota(store=store, quota_key="widgets", limit=5)

    def run():
        with transaction.atomic(using="default"):
            entitlements.check_quota(store=store, quota_key="widgets")

    _in_context(store, run)  # no raise


def test_check_quota_blocks_at_limit(store):
    set_subscription_quota(store=store, quota_key="widgets", limit=1)

    def run_once():
        with transaction.atomic(using="default"):
            entitlements.check_quota(store=store, quota_key="widgets")

    _in_context(store, run_once)  # consumes the only slot

    def run_twice():
        with transaction.atomic(using="default"):
            entitlements.check_quota(store=store, quota_key="widgets")

    with pytest.raises(entitlements.QuotaExceededError):
        _in_context(store, run_twice)


def test_check_quota_unconfigured_key_is_unenforced(store):
    def run():
        with transaction.atomic(using="default"):
            entitlements.check_quota(store=store, quota_key="nonexistent-quota-key")

    _in_context(store, run)  # no PlanVersionQuota row at all -- unenforced, not blocked


def test_check_quota_null_limit_is_unlimited(store):
    set_subscription_quota(store=store, quota_key="widgets", limit=None)

    def run():
        with transaction.atomic(using="default"):
            for _ in range(50):
                entitlements.check_quota(store=store, quota_key="widgets")

    _in_context(store, run)


# Note: `check_quota`'s "must be called inside transaction.atomic()"
# assertion is not independently unit-testable under this project's
# non-transactional `pytest.mark.django_db` mode (every test already
# runs inside an outer atomic block for isolation, same reason
# `transaction=True` is avoided project-wide -- see apps/orders/tests/
# test_concurrency.py's module docstring). It remains a real production
# safety net, just not one this harness can exercise in the negative.


# -- require_feature -----------------------------------------------------------


def test_require_feature_passes_when_enabled(store):
    set_subscription_feature(store=store, feature_key="api_access", enabled=True)
    _in_context(store, lambda: entitlements.require_feature(store=store, feature_key="api_access"))


def test_require_feature_raises_when_disabled(store):
    set_subscription_feature(store=store, feature_key="custom_domain", enabled=False)
    with pytest.raises(entitlements.FeatureNotEntitledError):
        _in_context(
            store, lambda: entitlements.require_feature(store=store, feature_key="custom_domain")
        )


def test_require_feature_raises_when_never_configured(store):
    with pytest.raises(entitlements.FeatureNotEntitledError):
        _in_context(
            store, lambda: entitlements.require_feature(store=store, feature_key="totally-unknown")
        )


# -- require_active_store -------------------------------------------------------


def test_require_active_store_passes_for_active_store(store):
    entitlements.require_active_store(store=store)  # no raise


def test_require_active_store_rejects_read_only_store(store):
    from apps.stores.models import Store

    store.status = Store.Status.READ_ONLY
    # Store's UPDATE RLS policy is self-scoped (id = current tenant
    # context) -- must be set here, same as any other Store mutation.
    _in_context(store, lambda: store.save(update_fields=["status", "updated_at"]))
    with pytest.raises(entitlements.StoreNotPurchasableError):
        entitlements.require_active_store(store=store)


# -- Cross-tenant: Store A's quota configuration/usage must never leak into
#    or affect Store B's entitlement check (approved architecture decision,
#    "cross-tenant entitlement checks" required test).
# --------------------------------------------------------------------------


def test_check_quota_never_reads_another_stores_subscription():
    store_a = create_bare_store("ent-cross-a")
    store_b = create_bare_store("ent-cross-b")

    set_subscription_quota(store=store_a, quota_key="widgets", limit=1)
    set_subscription_quota(store=store_b, quota_key="widgets", limit=100)

    def consume_a():
        with transaction.atomic(using="default"):
            entitlements.check_quota(store=store_a, quota_key="widgets")

    _in_context(store_a, consume_a)  # store A now at its limit (1/1)

    # Store B, with a much higher limit and zero usage of its own, must be
    # completely unaffected by store A's state.
    def consume_b():
        with transaction.atomic(using="default"):
            for _ in range(10):
                entitlements.check_quota(store=store_b, quota_key="widgets")

    _in_context(store_b, consume_b)  # no raise -- proves no cross-tenant leakage
