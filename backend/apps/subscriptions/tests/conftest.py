"""Shared test helpers for apps.subscriptions and its quota-integration tests."""

from __future__ import annotations

import psycopg
from django.db import connections

from apps.core.uuid7 import uuid7
from apps.stores.models import Store
from apps.subscriptions.models import Subscription
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db


def _current_subscription(store: Store) -> Subscription:
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return Subscription.objects.select_related("plan_version__plan").get(store=store)
        finally:
            clear_tenant_context_from_db()


def _publish_version_and_repoint(
    *,
    store: Store,
    quota: tuple[str, int | None] | None = None,
    feature: tuple[str, bool] | None = None,
):
    """
    Plan/PlanVersion/PlanVersionFeature/PlanVersionQuota are writable ONLY
    via `app_migrator` (approved architecture decision 1 -- RLS has no
    INSERT/UPDATE/DELETE policy for app_user on these tables at all).

    Uses a RAW, autocommit `psycopg` connection (the same pattern
    apps/orders/tests/test_concurrency.py's `_insert_store` uses for
    privileged setup), not Django's `.using("migrator")` ORM alias --
    `.using("migrator")` would still run inside pytest-django's own
    long-running, never-committed transaction for that alias (standard
    `TestCase`/`pytest.mark.django_db` isolation, applied to EVERY
    declared alias, not just "default"), so it would be just as invisible
    to "default" as this whole helper exists to work around.

    Crucially, the Subscription repoint below happens via the ORDINARY
    "default" ORM connection, NOT this raw one: the Subscription row
    itself was created earlier via "default" inside THIS test's still-
    open, uncommitted transaction (`create_bare_store`), so the raw
    migrator connection -- a genuinely separate session -- cannot see or
    UPDATE it (proven directly: that WHERE-matched zero rows when tried).
    "default" CAN see the raw connection's just-committed PlanVersion row
    on its own very next statement (PostgreSQL READ COMMITTED takes a
    fresh snapshot per statement, not per transaction), so doing the
    repoint there is what actually works.
    """
    subscription = _current_subscription(store)
    plan_id = subscription.plan_version.plan_id
    old_version = subscription.plan_version

    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        new_version_id = str(uuid7())
        conn.execute(
            "INSERT INTO subscriptions_planversion "
            "(id, created_at, updated_at, plan_id, version_number, price_monthly, "
            "price_yearly, currency, is_current, published_at) "
            "VALUES (%s, now(), now(), %s, "
            "(SELECT COALESCE(MAX(version_number), 0) + 1 FROM subscriptions_planversion "
            " WHERE plan_id = %s), "
            "%s, %s, %s, false, now())",
            [
                new_version_id,
                plan_id,
                plan_id,
                old_version.price_monthly,
                old_version.price_yearly,
                old_version.currency,
            ],
        )
        if quota is not None:
            quota_key, limit = quota
            conn.execute(
                "INSERT INTO subscriptions_planversionquota "
                '(id, created_at, updated_at, plan_version_id, quota_key, "limit", '
                "overage_policy) VALUES (%s, now(), now(), %s, %s, %s, 'block')",
                [str(uuid7()), new_version_id, quota_key, limit],
            )
        if feature is not None:
            feature_key, enabled = feature
            conn.execute(
                "INSERT INTO subscriptions_planversionfeature "
                "(id, created_at, updated_at, plan_version_id, feature_key, enabled) "
                "VALUES (%s, now(), now(), %s, %s, %s)",
                [str(uuid7()), new_version_id, feature_key, enabled],
            )
    finally:
        conn.close()

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            Subscription.objects.filter(id=subscription.id).update(plan_version_id=new_version_id)
        finally:
            clear_tenant_context_from_db()
    return new_version_id


def set_subscription_quota(*, store: Store, quota_key: str, limit: int | None) -> None:
    """
    Points `store`'s Subscription at a FRESH `PlanVersion` carrying the
    given quota limit -- never mutates an existing `PlanVersionQuota` row
    in place, matching the immutability discipline
    apps.subscriptions.services enforces everywhere else. Any OTHER
    quota_key simply has no row on the new version, i.e. unenforced --
    fine for tests that only care about one quota key at a time. Real
    COMMIT (see `_publish_version_and_repoint`), so the change is visible
    to production code's own "default"-alias reads within the same test.
    """
    _publish_version_and_repoint(store=store, quota=(quota_key, limit))


def set_subscription_feature(*, store: Store, feature_key: str, enabled: bool) -> None:
    _publish_version_and_repoint(store=store, feature=(feature_key, enabled))


def create_bare_store(slug: str) -> Store:
    """A Store with only what `create_store`'s hooks give it (a real trial
    Subscription) -- no owner/membership/domain, for tests that don't need
    the dashboard HTTP surface."""
    from apps.stores import hooks

    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            store = Store.objects.create(name=slug, slug=slug, status=Store.Status.ACTIVE)
        finally:
            clear_tenant_context_from_db()

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            hooks.run_post_creation_hooks(store=store)
        finally:
            clear_tenant_context_from_db()
    return store
