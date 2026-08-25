"""
Subscription lifecycle -- the runtime business-service layer, which
`app_user` (the role every request/task actually connects as) can fully
execute against `Subscription`/`Invoice` (standard tenant-owned RLS).
Business logic kept out of views, same discipline as every other app in
this project.

Deliberately does NOT include Plan/PlanVersion mutation (approved review
decision, docs/PHASE_10_REPORT.md): `Plan`/`PlanVersion`/
`PlanVersionFeature`/`PlanVersionQuota` are platform-global tables with
NO write policy for `app_user` at all (approved architecture decision
1). `app_migrator` exists to own the schema and run controlled
migrations/seed data -- it is NOT a runtime platform-admin bypass, and
this module (the layer ordinary application code calls into) must never
open that alias to perform a business mutation. Publishing a new
PlanVersion is an administrative action with no reviewed Platform Admin
write architecture yet (deferred to its own roadmap phase); until then
it happens ONLY through migrations, fixtures, or the explicit,
manually-run `manage.py publish_plan_version` command (see
apps/subscriptions/management/commands/publish_plan_version.py), never
through a service function importable/callable from request-serving code.

Scope note (approved architecture decision 15 -- read
docs/PHASE_10_REPORT.md for the full reasoning): docs/ARCHITECTURE.md's
Phase 10 DoD is "quota enforcement works on every applicable path", not
"platform subscription charging works" -- no platform payment-provider
integration exists yet, so `mark_past_due`/`mark_active` below are real,
independently unit-tested FSM transitions with NO live trigger calling
them from an actual payment event in this phase (mirrors the "staff"
quota gap: modeled and testable, not yet wired to a real event source).
What IS fully wired and tested is the time-based lifecycle path (trial
expiry, period-end-without-renewal -- apps.subscriptions.tasks), which
needs no external provider at all.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.stores.models import Store
from apps.subscriptions.models import Invoice, Plan, PlanVersion, Subscription


class NoDefaultTrialPlanError(Exception):
    """Raised if `Plan.objects.get(is_default_trial=True)` finds none --
    a deployment/seed-data precondition, not a user-facing error. See
    apps/subscriptions/migrations/0002_seed_default_trial_plan.py."""


def get_default_trial_plan_version() -> PlanVersion:
    try:
        plan = Plan.objects.get(is_default_trial=True)
    except Plan.DoesNotExist as exc:
        raise NoDefaultTrialPlanError(
            "No Plan has is_default_trial=True -- the platform has no seeded "
            "trial plan to provision new stores with."
        ) from exc
    return PlanVersion.objects.get(plan=plan, is_current=True)


def provision_trial_subscription(*, store: Store) -> Subscription:
    """Called from `apps.stores.services.create_store`, inside that
    function's SAME atomic transaction/tenant context -- approved
    architecture decision 12: a Store must never exist with no
    deterministic entitlement state, so this either succeeds alongside
    Store/StoreDomain/owner StoreMembership, or all of it rolls back
    together (`NoDefaultTrialPlanError` included)."""
    plan_version = get_default_trial_plan_version()
    now = timezone.now()
    trial_days = plan_version.plan.trial_days
    if trial_days > 0:
        status = Subscription.Status.TRIALING
        trial_ends_at = now + timedelta(days=trial_days)
        period_end = trial_ends_at
    else:
        status = Subscription.Status.ACTIVE
        trial_ends_at = None
        period_end = now + timedelta(days=30)

    return Subscription.objects.create(
        store=store,
        plan_version=plan_version,
        status=status,
        current_period_start=now,
        current_period_end=period_end,
        trial_ends_at=trial_ends_at,
    )


def upgrade_subscription(*, subscription: Subscription, plan_version: PlanVersion) -> Subscription:
    """Immediate (approved architecture decision 4): the new, higher
    limits/features apply on the very next `entitlements.check_quota`/
    `require_feature` call -- no proration engine, out of Phase 10 scope."""
    subscription.plan_version = plan_version
    subscription.save(update_fields=["plan_version", "updated_at"])
    return subscription


def schedule_downgrade(*, subscription: Subscription, plan_version: PlanVersion) -> Subscription:
    """Effective at `current_period_end` (approved architecture decision
    4) -- an immediate downgrade could put a merchant over quota in the
    middle of a period they already paid for. Applied by
    `apps.subscriptions.tasks.apply_subscription_lifecycle_transitions`
    at rollover, never before. Does NOT retroactively touch any
    already-created resource (approved architecture decision 2) -- see
    `apps.subscriptions.entitlements.check_quota`, which only ever blocks
    a NEW usage-increasing mutation, never an existing row."""
    subscription.scheduled_plan_version = plan_version
    subscription.save(update_fields=["scheduled_plan_version", "updated_at"])
    return subscription


def mark_past_due(*, subscription: Subscription) -> Subscription:
    if subscription.status == Subscription.Status.PAST_DUE:
        return subscription
    subscription.status = Subscription.Status.PAST_DUE
    subscription.past_due_since = timezone.now()
    subscription.save(update_fields=["status", "past_due_since", "updated_at"])
    return subscription


def mark_active(*, subscription: Subscription) -> Subscription:
    subscription.status = Subscription.Status.ACTIVE
    subscription.past_due_since = None
    subscription.save(update_fields=["status", "past_due_since", "updated_at"])
    return subscription


def cancel_subscription(*, subscription: Subscription) -> Subscription:
    """
    Immediate cancellation -- distinct from `Subscription.cancel_at`
    (a scheduled future cancellation set elsewhere, applied by the
    rollover task), same shape as `mark_active`/`mark_past_due` above.
    Added for Phase 14 (apps.platform_admin's explicit "cancel"
    action), but deliberately kept here rather than in
    apps.platform_admin: cancellation is a Subscription FSM transition
    like the other two, not a platform-privilege concern -- only WHO can
    call it (platform staff, via a Subscription instance fetched through
    the `platform` DB alias) is Phase 14-specific, not the transition
    itself."""
    subscription.status = Subscription.Status.CANCELED
    subscription.save(update_fields=["status", "updated_at"])
    return subscription


def issue_invoice_for_period(*, subscription: Subscription) -> Invoice:
    plan_version = subscription.plan_version
    amount = (
        plan_version.price_yearly
        if subscription.billing_interval == Subscription.BillingInterval.YEARLY
        else plan_version.price_monthly
    )
    return Invoice.objects.create(
        store=subscription.store,
        subscription=subscription,
        plan_version=plan_version,
        amount=amount,
        currency=plan_version.currency,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
    )


def mark_invoice_paid(*, invoice: Invoice) -> Invoice:
    """Merchant/dashboard-triggered, same "acceptance vs collection" shape
    as `apps.payments`' manual COD capture (no platform billing-provider
    webhook exists yet to do this automatically -- approved architecture
    decision 15)."""
    invoice.status = Invoice.Status.PAID
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=["status", "paid_at", "updated_at"])
    return invoice
