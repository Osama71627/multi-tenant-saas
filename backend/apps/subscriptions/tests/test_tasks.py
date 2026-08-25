"""
Phase 10 -- the time-based Subscription lifecycle sweep
(apps.subscriptions.tasks), the one lifecycle path fully wired without
needing a platform payment-provider integration (see
apps/subscriptions/services.py's module docstring).
`CELERY_TASK_ALWAYS_EAGER=True` (config/settings/test.py) runs these
synchronously, same pattern as apps/payments/tests/test_reconciliation.py.
"""

from __future__ import annotations

from datetime import timedelta

import psycopg
import pytest
from django.db import connections
from django.utils import timezone

from apps.core.uuid7 import uuid7
from apps.stores.models import Store
from apps.subscriptions import services, tasks
from apps.subscriptions.models import Invoice, PlanVersion, Subscription
from apps.subscriptions.tests.conftest import create_bare_store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


def _in_context(store, fn):
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return fn()
        finally:
            clear_tenant_context_from_db()


def _get_subscription(store) -> Subscription:
    return _in_context(
        store, lambda: Subscription.objects.select_related("plan_version__plan").get(store=store)
    )


def _save_subscription(store, subscription: Subscription, fields: list[str]) -> None:
    _in_context(store, lambda: subscription.save(update_fields=[*fields, "updated_at"]))


def _get_store(store_id) -> Store:
    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            return Store.objects.get(id=store_id)
        finally:
            clear_tenant_context_from_db()


def _publish_committed_paid_version(plan_id, *, price_monthly: int) -> str:
    """Creates a real, COMMITTED PlanVersion (raw autocommit migrator
    connection -- same reasoning as conftest.py's `_publish_version_and_repoint`),
    then returns its id so the caller can fetch it via the ordinary
    "default" connection (open SELECT) and pass it to
    `services.upgrade_subscription`/`schedule_downgrade` like real
    platform-admin code would."""
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        version_id = str(uuid7())
        conn.execute(
            "INSERT INTO subscriptions_planversion "
            "(id, created_at, updated_at, plan_id, version_number, price_monthly, "
            "price_yearly, currency, is_current, published_at) "
            "VALUES (%s, now(), now(), %s, "
            "(SELECT COALESCE(MAX(version_number), 0) + 1 FROM subscriptions_planversion "
            " WHERE plan_id = %s), %s, %s, 'SAR', false, now())",
            [version_id, plan_id, plan_id, price_monthly, price_monthly * 10],
        )
        return version_id
    finally:
        conn.close()


# -- Trial expiry -----------------------------------------------------------


def test_trial_expiry_moves_subscription_to_past_due():
    store = create_bare_store("task-trial-expiry")
    subscription = _get_subscription(store)
    subscription.trial_ends_at = timezone.now() - timedelta(hours=1)
    _save_subscription(store, subscription, ["trial_ends_at"])

    dispatched = tasks.apply_subscription_lifecycle_transitions()
    assert dispatched == 1

    refreshed = _get_subscription(store)
    assert refreshed.status == Subscription.Status.PAST_DUE
    assert refreshed.past_due_since is not None


def test_trial_not_yet_expired_is_left_alone():
    store = create_bare_store("task-trial-not-expired")
    tasks.apply_subscription_lifecycle_transitions()

    refreshed = _get_subscription(store)
    assert refreshed.status == Subscription.Status.TRIALING


# -- Past-due grace period ----------------------------------------------------


def test_past_due_beyond_grace_period_makes_store_read_only():
    store = create_bare_store("task-grace-exceeded")
    subscription = _get_subscription(store)
    grace_days = subscription.plan_version.plan.grace_period_days
    subscription.status = Subscription.Status.PAST_DUE
    subscription.past_due_since = timezone.now() - timedelta(days=grace_days + 1)
    _save_subscription(store, subscription, ["status", "past_due_since"])

    tasks.apply_subscription_lifecycle_transitions()

    assert _get_store(store.id).status == Store.Status.READ_ONLY


def test_past_due_within_grace_period_leaves_store_active():
    store = create_bare_store("task-grace-not-exceeded")
    subscription = _get_subscription(store)
    subscription.status = Subscription.Status.PAST_DUE
    subscription.past_due_since = timezone.now()
    _save_subscription(store, subscription, ["status", "past_due_since"])

    tasks.apply_subscription_lifecycle_transitions()

    assert _get_store(store.id).status == Store.Status.ACTIVE


# -- Canceled subscription -----------------------------------------------------


def test_canceled_subscription_past_period_end_makes_store_read_only():
    store = create_bare_store("task-canceled-expired")
    subscription = _get_subscription(store)
    subscription.status = Subscription.Status.CANCELED
    subscription.current_period_end = timezone.now() - timedelta(hours=1)
    _save_subscription(store, subscription, ["status", "current_period_end"])

    tasks.apply_subscription_lifecycle_transitions()

    assert _get_store(store.id).status == Store.Status.READ_ONLY


# -- Active subscription period rollover -----------------------------------


def test_active_subscription_past_period_end_rolls_the_period_forward():
    store = create_bare_store("task-rollover")
    subscription = _get_subscription(store)
    subscription.status = Subscription.Status.ACTIVE
    old_start = timezone.now() - timedelta(days=31)
    old_end = timezone.now() - timedelta(hours=1)
    subscription.current_period_start = old_start
    subscription.current_period_end = old_end
    _save_subscription(
        store, subscription, ["status", "current_period_start", "current_period_end"]
    )

    tasks.apply_subscription_lifecycle_transitions()

    refreshed = _get_subscription(store)
    assert refreshed.current_period_start == old_end  # new period starts where the old one ended
    assert refreshed.current_period_end > old_end
    # Trial plan is $0 -- no invoice for a free period.
    invoices = _in_context(store, lambda: list(Invoice.objects.filter(store=store)))
    assert invoices == []


def test_period_rollover_issues_an_invoice_for_a_paid_plan():
    store = create_bare_store("task-rollover-paid")
    subscription = _get_subscription(store)
    plan = subscription.plan_version.plan

    paid_version_id = _publish_committed_paid_version(plan.id, price_monthly=5000)
    paid_version = PlanVersion.objects.get(id=paid_version_id)  # visible: committed, open SELECT
    _in_context(
        store,
        lambda: services.upgrade_subscription(subscription=subscription, plan_version=paid_version),
    )

    subscription = _get_subscription(store)
    subscription.status = Subscription.Status.ACTIVE
    subscription.current_period_end = timezone.now() - timedelta(hours=1)
    _save_subscription(store, subscription, ["status", "current_period_end"])

    tasks.apply_subscription_lifecycle_transitions()

    invoices = _in_context(store, lambda: list(Invoice.objects.filter(store=store)))
    assert len(invoices) == 1
    assert invoices[0].amount == 5000
    assert invoices[0].status == Invoice.Status.OPEN


def test_period_rollover_applies_a_scheduled_downgrade():
    store = create_bare_store("task-rollover-downgrade")
    subscription = _get_subscription(store)
    plan = subscription.plan_version.plan

    downgrade_version_id = _publish_committed_paid_version(plan.id, price_monthly=0)
    downgrade_version = PlanVersion.objects.get(id=downgrade_version_id)
    _in_context(
        store,
        lambda: services.schedule_downgrade(
            subscription=subscription, plan_version=downgrade_version
        ),
    )

    subscription = _get_subscription(store)
    assert subscription.scheduled_plan_version_id == downgrade_version.id
    subscription.status = Subscription.Status.ACTIVE
    subscription.current_period_end = timezone.now() - timedelta(hours=1)
    _save_subscription(store, subscription, ["status", "current_period_end"])

    tasks.apply_subscription_lifecycle_transitions()

    refreshed = _get_subscription(store)
    assert refreshed.plan_version_id == downgrade_version.id
    assert refreshed.scheduled_plan_version_id is None
