"""
Unit coverage for apps.subscriptions.services -- the FSM helpers and
Invoice lifecycle that `apps/subscriptions/tests/test_tasks.py` doesn't
already exercise indirectly through the sweep task.
"""

from __future__ import annotations

import psycopg
import pytest
from django.db import connections

from apps.subscriptions import services
from apps.subscriptions.models import Invoice, Subscription
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
    return _in_context(store, lambda: Subscription.objects.get(store=store))


def test_mark_past_due_sets_status_and_timestamp():
    store = create_bare_store("svc-mark-past-due")
    subscription = _get_subscription(store)

    updated = _in_context(store, lambda: services.mark_past_due(subscription=subscription))

    assert updated.status == Subscription.Status.PAST_DUE
    assert updated.past_due_since is not None


def test_mark_past_due_is_idempotent():
    store = create_bare_store("svc-mark-past-due-idem")
    subscription = _get_subscription(store)
    _in_context(store, lambda: services.mark_past_due(subscription=subscription))
    first_timestamp = _get_subscription(store).past_due_since

    subscription = _get_subscription(store)
    _in_context(store, lambda: services.mark_past_due(subscription=subscription))

    assert _get_subscription(store).past_due_since == first_timestamp  # unchanged, no-op


def test_mark_active_clears_past_due_state():
    store = create_bare_store("svc-mark-active")
    subscription = _get_subscription(store)
    _in_context(store, lambda: services.mark_past_due(subscription=subscription))

    subscription = _get_subscription(store)
    updated = _in_context(store, lambda: services.mark_active(subscription=subscription))

    assert updated.status == Subscription.Status.ACTIVE
    assert updated.past_due_since is None


def test_issue_invoice_for_period_snapshots_the_current_plan_version():
    store = create_bare_store("svc-issue-invoice")
    subscription = _get_subscription(store)

    invoice = _in_context(
        store, lambda: services.issue_invoice_for_period(subscription=subscription)
    )

    assert invoice.status == Invoice.Status.OPEN
    assert invoice.plan_version_id == subscription.plan_version_id
    assert invoice.period_start == subscription.current_period_start
    assert invoice.period_end == subscription.current_period_end
    assert invoice.amount == subscription.plan_version.price_monthly


def test_mark_invoice_paid_sets_status_and_timestamp():
    store = create_bare_store("svc-mark-invoice-paid")
    subscription = _get_subscription(store)
    invoice = _in_context(
        store, lambda: services.issue_invoice_for_period(subscription=subscription)
    )

    paid = _in_context(store, lambda: services.mark_invoice_paid(invoice=invoice))

    assert paid.status == Invoice.Status.PAID
    assert paid.paid_at is not None


def test_get_default_trial_plan_version_returns_the_seeded_plan():
    version = services.get_default_trial_plan_version()
    assert version.plan.is_default_trial is True
    assert version.is_current is True


def test_provision_trial_subscription_with_a_zero_trial_days_plan_starts_active():
    """The default seeded plan has `trial_days=14`, so every other test in
    this suite exercises the `trial_days > 0` branch of
    `provision_trial_subscription` -- this proves the other branch: a
    plan with no trial period starts a Subscription straight at `active`,
    never `trialing`."""
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        conn.execute("UPDATE subscriptions_plan SET trial_days = 0 WHERE code = 'trial'")
        store = create_bare_store("svc-zero-trial-days")
    finally:
        conn.execute("UPDATE subscriptions_plan SET trial_days = 14 WHERE code = 'trial'")
        conn.close()

    subscription = _get_subscription(store)
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.trial_ends_at is None
