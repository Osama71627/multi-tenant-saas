"""Registers apps.subscriptions TenantOwnedModels with the generic isolation test suite."""

from datetime import timedelta

from django.utils import timezone

from apps.subscriptions.models import Invoice, Plan, PlanVersion, Subscription, UsageRecord
from apps.tenancy.testing import register


def _plan_version(suffix: str) -> PlanVersion:
    # Plan/PlanVersion are writable ONLY via app_migrator (approved
    # architecture decision 1) -- this factory runs through the ordinary
    # app_user-bound "default" connection (see
    # backend/tests/test_tenant_isolation.py's `_create_row_for`), so it
    # must reuse the already-seeded default trial PlanVersion
    # (apps/subscriptions/migrations/0002_seed_default_trial_plan.py)
    # rather than creating a new one -- reading it is fine (open SELECT).
    plan = Plan.objects.get(is_default_trial=True)
    return PlanVersion.objects.get(plan=plan, is_current=True)


def _make_subscription(store, suffix: str) -> Subscription:
    now = timezone.now()
    return Subscription.objects.create(
        store=store,
        plan_version=_plan_version(suffix),
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )


@register(Subscription)
def _subscription_factory(store, suffix: str) -> Subscription:
    return _make_subscription(store, suffix)


@register(UsageRecord)
def _usage_record_factory(store, suffix: str) -> UsageRecord:
    now = timezone.now()
    return UsageRecord.objects.create(
        store=store,
        quota_key=f"quota-{suffix}",
        period_start=now,
        period_end=now + timedelta(days=30),
    )


@register(Invoice)
def _invoice_factory(store, suffix: str) -> Invoice:
    subscription = _make_subscription(store, suffix)
    now = timezone.now()
    return Invoice.objects.create(
        store=store,
        subscription=subscription,
        plan_version=subscription.plan_version,
        amount=1000,
        currency="SAR",
        period_start=now,
        period_end=now + timedelta(days=30),
    )
