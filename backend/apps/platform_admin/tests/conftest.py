"""
Real cross-connection test fixtures for apps.platform_admin.

`platform` (`app_platform_admin`) and `default` (`app_user`) are
genuinely separate PostgreSQL sessions in a running app -- and
pytest-django wraps EACH declared alias in its OWN uncommitted per-test
transaction, so a Store created via plain `Store.objects.create()` on
"default" is invisible to a query on "platform" within the same test
(verified empirically: `Store.objects.using("platform")` sees nothing
until the "default"-side transaction actually commits, which a rolled-
back test never does). Same proven pattern as
apps/orders/tests/test_concurrency.py's `_insert_store`: seed via a raw,
autocommitting `psycopg` connection using `app_migrator` (real commits),
so every alias's own session sees the row via ordinary PostgreSQL MVCC,
not test-transaction trickery.

Cleanup is deliberately deferred to a PACKAGE-scoped fixture (runs once,
after the LAST test under apps/platform_admin/tests/ finishes), not done
per-test: a test that mutates a fixture-created row via the ORM (e.g.
`services.suspend_store`, which writes through pytest-django's own
long-lived per-test "platform" transaction) holds a real row lock until
THAT transaction rolls back at the end of the individual test function --
a raw autocommit DELETE in a per-test teardown trying to touch the same
row blocks waiting for a lock that can't release until the very fixture
that's blocking finishes (a real, reproduced deadlock during development
of this file). By the time the LAST test in this package finishes, every
earlier test's transaction has already rolled back, so a single bulk
cleanup here is deadlock-free.

Package scope (not session scope) matters for a second reason, also
found empirically: these are REAL commits, visible for the rest of the
pytest session to OTHER apps' tests that scan broadly across all
stores/subscriptions (e.g. apps.subscriptions.tasks' lifecycle sweep,
`Store.objects.filter(status__in=[ACTIVE, READ_ONLY])` with no per-test
isolation possible). Session-scoped cleanup still leaves that pollution
in place for the ENTIRE run up until the very end -- broke
apps/subscriptions/tests/test_tasks.py's exact dispatched-count assertion
when the full suite ran with platform_admin's tests (which sort earlier
alphabetically) executing first. Package scope cleans up as soon as this
package's own tests are done, before any later-sorted package's tests
that might assume a clean slate get to run.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg
import pytest
from django.db import connections

from apps.core.uuid7 import uuid7


def _migrator_conn() -> psycopg.Connection:
    params = connections["migrator"].get_connection_params()
    return psycopg.connect(**params, autocommit=True)


@pytest.fixture(scope="package")
def _platform_admin_test_registry():
    registry = {"stores": [], "subscriptions": [], "users": [], "orders": []}
    yield registry
    with _migrator_conn() as conn:
        for order_id in registry["orders"]:
            conn.execute("DELETE FROM orders_order WHERE id = %s", [order_id])
        for subscription_id in registry["subscriptions"]:
            conn.execute("DELETE FROM subscriptions_subscription WHERE id = %s", [subscription_id])
        for store_id in registry["stores"]:
            conn.execute("DELETE FROM orders_order WHERE store_id = %s", [store_id])
            conn.execute("DELETE FROM subscriptions_subscription WHERE store_id = %s", [store_id])
            conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        for user_id in registry["users"]:
            conn.execute("DELETE FROM accounts_platformuser WHERE id = %s", [user_id])


@pytest.fixture
def make_store(_platform_admin_test_registry) -> Callable[..., str]:
    def _make(name: str, slug: str, status: str = "active") -> str:
        store_id = str(uuid7())
        with _migrator_conn() as conn:
            conn.execute(
                "INSERT INTO stores_store "
                "(id, created_at, updated_at, name, slug, status, default_currency, "
                "contact_email, contact_phone) "
                "VALUES (%s, now(), now(), %s, %s, %s, 'SAR', '', '')",
                [store_id, name, slug, status],
            )
        _platform_admin_test_registry["stores"].append(store_id)
        return store_id

    return _make


@pytest.fixture
def make_subscription(_platform_admin_test_registry) -> Callable[..., str]:
    def _make(store_id: str, status: str = "trialing") -> str:
        with _migrator_conn() as conn:
            row = conn.execute(
                "SELECT id FROM subscriptions_planversion WHERE is_current = true "
                "ORDER BY published_at LIMIT 1"
            ).fetchone()
            assert (
                row is not None
            ), "No current PlanVersion seeded -- check the default trial plan seed."
            (plan_version_id,) = row
            subscription_id = str(uuid7())
            conn.execute(
                "INSERT INTO subscriptions_subscription "
                "(id, created_at, updated_at, store_id, plan_version_id, status, "
                "billing_interval, current_period_start, current_period_end, provider_ref) "
                "VALUES (%s, now(), now(), %s, %s, %s, 'monthly', now(), "
                "now() + interval '30 days', '')",
                [subscription_id, store_id, plan_version_id, status],
            )
        _platform_admin_test_registry["subscriptions"].append(subscription_id)
        return subscription_id

    return _make


@pytest.fixture
def make_order(_platform_admin_test_registry) -> Callable[..., str]:
    """Phase 15 -- a real, committed Order for platform-wide analytics
    tests (`apps.platform_admin.services.overview_metrics`'s
    `orders_total`/`revenue_by_currency`)."""

    def _make(
        store_id: str,
        *,
        number: str,
        status: str = "confirmed",
        total_amount: int = 1000,
        currency: str = "SAR",
    ) -> str:
        order_id = str(uuid7())
        with _migrator_conn() as conn:
            conn.execute(
                "INSERT INTO orders_order "
                "(id, created_at, updated_at, store_id, number, email, status, "
                "fulfillment_status, currency, subtotal_amount, discount_amount, "
                "tax_amount, shipping_amount, total_amount, shipping_address, "
                "shipping_method_name_snapshot, coupon_code_snapshot) "
                "VALUES (%s, now(), now(), %s, %s, 'buyer@example.com', %s, "
                "'unfulfilled', %s, %s, 0, 0, 0, %s, '{}', 'Standard', '')",
                [order_id, store_id, number, status, currency, total_amount, total_amount],
            )
        _platform_admin_test_registry["orders"].append(order_id)
        return order_id

    return _make


@pytest.fixture
def make_platform_staff_user(_platform_admin_test_registry) -> Callable[..., object]:
    from apps.accounts.models import PlatformUser

    def _make(email: str, *, is_platform_staff: bool = True, is_active: bool = True):
        with _migrator_conn() as conn:
            user_id = str(uuid7())
            conn.execute(
                "INSERT INTO accounts_platformuser "
                "(id, created_at, updated_at, password, last_login, email, full_name, "
                "is_active, is_staff, is_platform_staff, is_superuser, email_verified_at) "
                "VALUES (%s, now(), now(), '', NULL, %s, '', %s, false, %s, false, NULL)",
                [user_id, email, is_active, is_platform_staff],
            )
        _platform_admin_test_registry["users"].append(user_id)
        return PlatformUser.objects.using("platform").get(id=user_id)

    return _make
