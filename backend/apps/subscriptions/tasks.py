"""
Time-based Subscription lifecycle sweep -- the one lifecycle path fully
wired end-to-end in Phase 10 with no external payment-provider dependency
(see apps/subscriptions/services.py's module docstring on the
`mark_past_due`/`mark_active` scope gap). Two-task split mirrors
`apps.payments.tasks`' reconciliation shape (Phase 9), which itself
mirrors `apps.tenancy.celery`'s own PlatformTask/TenantTask split:
`apply_subscription_lifecycle_transitions` is a cross-tenant SCAN
(`PlatformTask`, read-only over `Store`), `_apply_one_store_transition` is
the actual per-store, RLS-scoped, transition-applying work (`TenantTask`,
dispatched via `dispatch_for_store`).

Three transitions, matching approved architecture decision 8's table:

  1. `trialing` past `trial_ends_at`, no plan chosen -> `past_due`.
  2. `past_due` past `past_due_since + plan.grace_period_days` -> the
     STORE (not the Subscription) becomes `read_only`.
  3. `active`/`canceled` past `current_period_end` with no cancellation
     pending renewal -> either roll the period forward (applying any
     `scheduled_plan_version` downgrade, approved decision 4) or, for a
     `canceled` Subscription, make the Store `read_only`.
"""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.stores.models import Store
from apps.subscriptions import services
from apps.subscriptions.models import Subscription
from apps.tenancy.celery import PlatformTask, TenantTask, dispatch_for_store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db


@shared_task(
    base=PlatformTask, name="apps.subscriptions.tasks.apply_subscription_lifecycle_transitions"
)
def apply_subscription_lifecycle_transitions() -> int:
    dispatched = 0
    for store in Store.objects.filter(status__in=[Store.Status.ACTIVE, Store.Status.READ_ONLY]):
        with tenant_context(TenantContext(store_id=store.id)):
            apply_tenant_context_to_db(store.id)
            try:
                if Subscription.objects.filter(store=store).exists():
                    dispatch_for_store(_apply_one_store_transition, store.id)
                    dispatched += 1
            finally:
                clear_tenant_context_from_db()
    return dispatched


@shared_task(base=TenantTask, name="apps.subscriptions.tasks._apply_one_store_transition")
def _apply_one_store_transition() -> None:
    subscription = Subscription.objects.select_related("plan_version__plan", "store").get()
    store = subscription.store
    now = timezone.now()

    if (
        subscription.status == Subscription.Status.TRIALING
        and subscription.trial_ends_at is not None
        and subscription.trial_ends_at <= now
    ):
        services.mark_past_due(subscription=subscription)
        return

    if subscription.status == Subscription.Status.PAST_DUE and subscription.past_due_since:
        grace = subscription.plan_version.plan.grace_period_days
        if subscription.past_due_since + timedelta(days=grace) <= now:
            if store.status != Store.Status.READ_ONLY:
                store.status = Store.Status.READ_ONLY
                store.save(update_fields=["status", "updated_at"])
        return

    if subscription.status == Subscription.Status.CANCELED:
        if subscription.current_period_end <= now and store.status != Store.Status.READ_ONLY:
            store.status = Store.Status.READ_ONLY
            store.save(update_fields=["status", "updated_at"])
        return

    if subscription.status == Subscription.Status.ACTIVE and subscription.current_period_end <= now:
        _roll_period_forward(subscription)


def _roll_period_forward(subscription: Subscription) -> None:
    if subscription.scheduled_plan_version is not None:
        subscription.plan_version = subscription.scheduled_plan_version
        subscription.scheduled_plan_version = None

    period_length = subscription.current_period_end - subscription.current_period_start
    subscription.current_period_start = subscription.current_period_end
    subscription.current_period_end = subscription.current_period_end + period_length
    subscription.save(
        update_fields=[
            "plan_version",
            "scheduled_plan_version",
            "current_period_start",
            "current_period_end",
            "updated_at",
        ]
    )

    plan_version = subscription.plan_version
    amount = (
        plan_version.price_yearly
        if subscription.billing_interval == Subscription.BillingInterval.YEARLY
        else plan_version.price_monthly
    )
    if amount > 0:
        services.issue_invoice_for_period(subscription=subscription)
