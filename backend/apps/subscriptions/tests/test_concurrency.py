"""
Real cross-connection concurrency (two genuinely separate PostgreSQL
sessions), same proven pattern as apps/orders/tests/test_concurrency.py
and apps/inventory/tests/test_overselling_concurrency.py:
`pytest.mark.django_db(transaction=True)` is avoided (`app_user` lacks
TRUNCATE); raw `psycopg` connections instead -- `app_migrator` for
setup/teardown with real commits, `app_user` for the competing attempts,
each running the EXACT SQL sequence the real service function runs.

Required by the Phase 10 approved architecture review (point 18, items
3 and 4):

1. "products" quota (category A -- live COUNT, `pg_advisory_xact_lock`):
   one remaining slot, two concurrent usage-increasing attempts, exactly
   one succeeds. Mirrors `apps.subscriptions.entitlements._check_live_count_quota`
   exactly.
2. "orders_per_period" quota (category B -- `UsageRecord` row lock):
   one remaining slot, two concurrent attempts, exactly one succeeds, no
   lost/duplicate increment. Mirrors
   `apps.subscriptions.entitlements._check_and_increment_usage_record`
   exactly (the same `SELECT ... FOR UPDATE` / `get_or_create` shape
   Phase 8's `OrderNumberSequence` concurrency test already proved safe
   for an analogous per-store counter).
"""

from __future__ import annotations

import threading
from datetime import timedelta

import psycopg
import pytest
from django.db import connections
from django.utils import timezone

from apps.core.uuid7 import uuid7

pytestmark = pytest.mark.django_db


def _insert_store(conn, store_id: str, slug: str) -> None:
    conn.execute(
        "INSERT INTO stores_store "
        "(id, created_at, updated_at, name, slug, status, default_currency, "
        "contact_email, contact_phone) "
        "VALUES (%s, now(), now(), 'Race Co', %s, 'active', 'SAR', '', '')",
        [store_id, slug],
    )


def _insert_subscription_with_quota(
    conn, *, store_id: str, quota_key: str, limit: int, period_days: int = 30
) -> None:
    """Seeds a Plan/PlanVersion/PlanVersionQuota/Subscription directly via
    the migrator connection (bypasses RLS as table owner -- legitimate
    privileged test setup, same as every other raw-connection fixture in
    this project)."""
    plan_id, version_id, quota_id, sub_id = (str(uuid7()) for _ in range(4))
    now = timezone.now()
    period_end = now + timedelta(days=period_days)
    conn.execute(
        "INSERT INTO subscriptions_plan "
        "(id, created_at, updated_at, code, name, is_public, trial_days, "
        "grace_period_days, is_default_trial) "
        "VALUES (%s, now(), now(), %s, 'Race Plan', true, 0, 3, false)",
        [plan_id, f"race-plan-{plan_id[:8]}"],
    )
    conn.execute(
        "INSERT INTO subscriptions_planversion "
        "(id, created_at, updated_at, plan_id, version_number, price_monthly, "
        "price_yearly, currency, is_current, published_at) "
        "VALUES (%s, now(), now(), %s, 1, 0, 0, 'SAR', true, now())",
        [version_id, plan_id],
    )
    conn.execute(
        "INSERT INTO subscriptions_planversionquota "
        '(id, created_at, updated_at, plan_version_id, quota_key, "limit", overage_policy) '
        "VALUES (%s, now(), now(), %s, %s, %s, 'block')",
        [quota_id, version_id, quota_key, limit],
    )
    conn.execute(
        "INSERT INTO subscriptions_subscription "
        "(id, created_at, updated_at, store_id, plan_version_id, status, billing_interval, "
        "current_period_start, current_period_end, trial_ends_at, past_due_since, cancel_at, "
        "provider_ref) "
        "VALUES (%s, now(), now(), %s, %s, 'active', 'monthly', %s, %s, NULL, NULL, NULL, '')",
        [sub_id, store_id, version_id, now, period_end],
    )


# --------------------------------------------------------------------------
# 1. "products" quota -- category A, pg_advisory_xact_lock boundary.
# --------------------------------------------------------------------------


def _attempt_create_product(user_params, store_id: str, limit: int) -> str:
    """The exact sequence `apps.subscriptions.entitlements._check_live_count_quota`
    + `apps.catalog.services.create_product` run, in raw SQL."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))", [store_id, "products"]
            )
            cur.execute(
                "SELECT COUNT(*) FROM catalog_product WHERE store_id = %s AND status != 'archived'",
                [store_id],
            )
            row = cur.fetchone()
            assert row is not None
            (current,) = row
            if current + 1 > limit:
                conn.rollback()
                return "rejected"

            product_id = str(uuid7())
            variant_id = str(uuid7())
            cur.execute(
                "INSERT INTO catalog_product (id, created_at, updated_at, name, slug, "
                "description, status, seo_title, seo_description, store_id) "
                "VALUES (%s, now(), now(), 'Race Widget', %s, '', 'draft', '', '', %s)",
                [product_id, f"race-{product_id[:8]}", store_id],
            )
            cur.execute(
                "INSERT INTO catalog_productvariant (id, created_at, updated_at, sku, status, "
                "is_default, position, currency, price_amount, barcode, option_signature, "
                "product_id, store_id) "
                "VALUES (%s, now(), now(), %s, 'active', true, 0, 'SAR', 1000, '', '{}', %s, %s)",
                [variant_id, f"RACE-{product_id[:8]}", product_id, store_id],
            )
        conn.commit()
        return "created"
    finally:
        conn.close()


def test_two_concurrent_product_creates_racing_for_the_last_slot_only_one_wins():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()
    store_id = str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"prod-race-{store_id[:8]}")
        _insert_subscription_with_quota(
            setup_conn, store_id=store_id, quota_key="products", limit=1
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(_attempt_create_product(user_params, store_id, 1))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["created", "rejected"], results

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM catalog_product WHERE store_id = %s AND status != 'archived'",
                [store_id],
            )
            (final_count,) = cur.fetchone()
        assert final_count == 1  # never crossed the limit, never lost the one winning create
    finally:
        setup_conn.execute("DELETE FROM catalog_productvariant WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM catalog_product WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM subscriptions_subscription WHERE store_id = %s", [store_id])
        setup_conn.execute(
            "DELETE FROM subscriptions_planversionquota WHERE plan_version_id IN "
            "(SELECT id FROM subscriptions_planversion WHERE plan_id IN "
            " (SELECT id FROM subscriptions_plan WHERE code LIKE 'race-plan-%'))"
        )
        setup_conn.execute(
            "DELETE FROM subscriptions_planversion WHERE plan_id IN "
            "(SELECT id FROM subscriptions_plan WHERE code LIKE 'race-plan-%')"
        )
        setup_conn.execute("DELETE FROM subscriptions_plan WHERE code LIKE 'race-plan-%'")
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# 2. "orders_per_period" quota -- category B, UsageRecord row lock boundary.
# --------------------------------------------------------------------------


def _select_usage_record_for_update(cur, store_id, period_start, period_end):
    cur.execute(
        "SELECT id, used FROM subscriptions_usagerecord "
        "WHERE store_id = %s AND quota_key = %s AND period_start = %s AND period_end = %s "
        "FOR UPDATE",
        [store_id, "orders_per_period", period_start, period_end],
    )
    return cur.fetchone()


def _attempt_consume_usage_record(
    user_params, store_id: str, period_start, period_end, limit: int
) -> str:
    """
    The exact `select_for_update().get_or_create()` + increment sequence
    `apps.subscriptions.entitlements._check_and_increment_usage_record`
    runs -- including Django's own `get_or_create` internal race handling:
    `SELECT ... FOR UPDATE` cannot lock a row that doesn't exist yet, so
    two concurrent first-ever attempts for the same period both fall
    through to INSERT; the `uniq_usage_record_per_period` constraint lets
    only one through, and Django's `get_or_create` catches that
    `IntegrityError` and re-`SELECT`s (now finding, and locking, the
    winner's row) rather than propagating it. A SAVEPOINT
    (`conn.transaction()`) is what lets this raw sequence catch the
    conflict without poisoning the rest of the outer transaction, exactly
    as Django's own atomic-wrapped `get_or_create` does internally.
    """
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            row = _select_usage_record_for_update(cur, store_id, period_start, period_end)
            if row is None:
                record_id = str(uuid7())
                try:
                    with conn.transaction():  # SAVEPOINT
                        cur.execute(
                            "INSERT INTO subscriptions_usagerecord "
                            "(id, created_at, updated_at, store_id, quota_key, period_start, "
                            "period_end, used) VALUES (%s, now(), now(), %s, %s, %s, %s, 0)",
                            [record_id, store_id, "orders_per_period", period_start, period_end],
                        )
                    used = 0
                except psycopg.errors.UniqueViolation:
                    # Lost the race to create -- re-SELECT ... FOR UPDATE, now
                    # locking the winner's already-committed row.
                    record_id, used = _select_usage_record_for_update(
                        cur, store_id, period_start, period_end
                    )
            else:
                record_id, used = row

            if used + 1 > limit:
                conn.rollback()
                return "rejected"

            cur.execute(
                "UPDATE subscriptions_usagerecord SET used = %s WHERE id = %s",
                [used + 1, record_id],
            )
        conn.commit()
        return "consumed"
    finally:
        conn.close()


def test_two_concurrent_checkouts_racing_for_the_last_order_slot_only_one_wins():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()
    store_id = str(uuid7())
    now = timezone.now()
    period_end = now + timedelta(days=30)

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"order-race-{store_id[:8]}")
        _insert_subscription_with_quota(
            setup_conn, store_id=store_id, quota_key="orders_per_period", limit=1
        )
        # The subscription's real period fields (used as the UsageRecord key)
        # -- read back so the raw attempts key against the SAME period the
        # setup helper actually wrote.
        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT current_period_start, current_period_end FROM subscriptions_subscription "
                "WHERE store_id = %s",
                [store_id],
            )
            period_start, period_end = cur.fetchone()

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(
                _attempt_consume_usage_record(user_params, store_id, period_start, period_end, 1)
            )

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["consumed", "rejected"], results

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT used FROM subscriptions_usagerecord "
                "WHERE store_id = %s AND quota_key = 'orders_per_period'",
                [store_id],
            )
            (final_used,) = cur.fetchone()
        assert final_used == 1  # exactly one increment landed, never 0, never 2
    finally:
        setup_conn.execute("DELETE FROM subscriptions_usagerecord WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM subscriptions_subscription WHERE store_id = %s", [store_id])
        setup_conn.execute(
            "DELETE FROM subscriptions_planversionquota WHERE plan_version_id IN "
            "(SELECT id FROM subscriptions_planversion WHERE plan_id IN "
            " (SELECT id FROM subscriptions_plan WHERE code LIKE 'race-plan-%'))"
        )
        setup_conn.execute(
            "DELETE FROM subscriptions_planversion WHERE plan_id IN "
            "(SELECT id FROM subscriptions_plan WHERE code LIKE 'race-plan-%')"
        )
        setup_conn.execute("DELETE FROM subscriptions_plan WHERE code LIKE 'race-plan-%'")
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()
