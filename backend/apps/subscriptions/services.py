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

import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import PlatformUser
from apps.stores.models import Store
from apps.stores.services import StoreSlugReservedError, create_store
from apps.subscriptions.models import (
    Invoice,
    Plan,
    PlanVersion,
    Subscription,
    SubscriptionCheckoutSession,
)


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


# --------------------------------------------------------------------------
# Phase D ("product vision reset" -- Plan Selection). SubscriptionCheckoutSession
# IS a normal app_user-writable table (not Plan/PlanVersion), so unlike
# everything above this comment, these functions are real runtime service
# code, callable from views -- see models.py's own docstring on why this
# table has no RLS/tenant-scoping (user-scoped, not store-scoped; there is
# no Store yet at this point in the journey).
# --------------------------------------------------------------------------


class PlanVersionNotAvailableError(Exception):
    """The requested PlanVersion doesn't exist, isn't its Plan's current
    version, or belongs to a non-public Plan -- a real client error
    (the merchant selected something no longer/never offered), not a
    deployment gap. Price/availability is ALWAYS re-derived from this
    check server-side; a client-supplied price is never trusted (the
    request only ever carries a `plan_version_id`, never an amount)."""


class NoActiveCheckoutSessionError(Exception):
    """Raised when an operation needs an existing draft/ready_for_payment
    session for this user and none exists -- e.g. selecting a plan
    before ever starting a checkout session at all."""


# Pre-payment only -- selecting/changing a plan must never be possible
# once a payment has actually succeeded (that would silently detach the
# price the user paid for from the plan they end up with). `payment_failed`
# is included on purpose: the approved Phase E failure screen offers
# "return to plan" (a merchant can pick a DIFFERENT plan after a decline,
# not just retry the same one) -- see billing.py's `_INITIATABLE_STATUSES`
# for the separate, narrower set that governs retrying PAYMENT itself.
# Used ONLY by `select_plan_for_checkout_session` below.
_PRE_PAYMENT_STATUSES = (
    SubscriptionCheckoutSession.CheckoutStatus.DRAFT,
    SubscriptionCheckoutSession.CheckoutStatus.READY_FOR_PAYMENT,
    SubscriptionCheckoutSession.CheckoutStatus.PAYMENT_FAILED,
)

# Everything short of a Store actually existing -- i.e. "this user has
# an in-progress checkout journey, don't start a second one, and let
# them see/update it". Phase E added `payment_pending`/`payment_failed`/
# `awaiting_business_info` to this set; the DB-level
# `uniq_active_checkout_session_per_user` constraint mirrors the same
# values for the same reason.
_OPEN_CHECKOUT_STATUSES = (
    *_PRE_PAYMENT_STATUSES,
    SubscriptionCheckoutSession.CheckoutStatus.PAYMENT_PENDING,
    SubscriptionCheckoutSession.CheckoutStatus.AWAITING_BUSINESS_INFO,
)


def get_active_checkout_session(*, user: PlatformUser) -> SubscriptionCheckoutSession | None:
    """The one open (not yet a Store) session for this user, if any --
    looked up purely by `user`, never by a client-held session id, so
    it survives a refresh or a fresh login exactly the same way (Phase D
    requirement: the choice must not depend on any client-side state
    surviving)."""
    return SubscriptionCheckoutSession.objects.filter(
        user=user, checkout_status__in=_OPEN_CHECKOUT_STATUSES
    ).first()


def start_or_update_checkout_session(
    *, user: PlatformUser, theme_preset_id=None
) -> SubscriptionCheckoutSession:
    """Upsert, not create-only: a user re-visiting the marketplace and
    picking a DIFFERENT theme updates their existing open session
    rather than accumulating a second one (enforced at the DB level too
    -- `uniq_active_checkout_session_per_user`) -- including one that
    already paid but hasn't submitted business info yet: changing the
    theme post-payment is harmless (price depends on the plan, not the
    theme). Picking a plan later does not require having passed a theme
    here; `theme_preset_id` is optional so a session can exist (e.g. mid
    plan-selection) with no theme attached yet if a caller ever reaches
    this without one."""
    with transaction.atomic():
        session = (
            SubscriptionCheckoutSession.objects.select_for_update()
            .filter(user=user, checkout_status__in=_OPEN_CHECKOUT_STATUSES)
            .first()
        )
        if session is None:
            session = SubscriptionCheckoutSession.objects.create(
                user=user, theme_preset_id=theme_preset_id
            )
        elif theme_preset_id is not None and session.theme_preset_id != theme_preset_id:
            session.theme_preset_id = theme_preset_id
            session.save(update_fields=["theme_preset_id", "updated_at"])
        return session


def select_plan_for_checkout_session(
    *, user: PlatformUser, plan_version_id
) -> SubscriptionCheckoutSession:
    """Validates the plan server-side (real availability + real price,
    from `PlanVersion`/`Plan` -- never from anything the client sent)
    before attaching it to the user's active session. Raises rather
    than silently ignoring an invalid/unavailable plan_version_id, so
    the view can surface a real 4xx instead of pretending it worked."""
    try:
        plan_version = PlanVersion.objects.select_related("plan").get(
            id=plan_version_id, is_current=True, plan__is_public=True
        )
    except PlanVersion.DoesNotExist as exc:
        raise PlanVersionNotAvailableError(
            f"PlanVersion {plan_version_id!r} is not a current, public plan."
        ) from exc

    with transaction.atomic():
        session = (
            SubscriptionCheckoutSession.objects.select_for_update()
            .filter(user=user, checkout_status__in=_PRE_PAYMENT_STATUSES)
            .first()
        )
        if session is None:
            raise NoActiveCheckoutSessionError(
                "No active checkout session for this user -- start one "
                "(e.g. by selecting a theme) before selecting a plan."
            )
        session.plan_version = plan_version
        session.checkout_status = SubscriptionCheckoutSession.CheckoutStatus.READY_FOR_PAYMENT
        session.save(update_fields=["plan_version", "checkout_status", "updated_at"])
        return session


# --------------------------------------------------------------------------
# Phase E (payment, demo/sandbox only) + F (business info) -- "product
# vision reset" continued. See settings.SUBSCRIPTION_BILLING_MODE's
# two-gate comment (config/settings/base.py) for why a demo payment can
# ever run at all, and Store's field comments (apps/stores/models.py)
# for why business info lands directly on the Store row it produces.
# --------------------------------------------------------------------------


class CheckoutNotAwaitingBusinessInfoError(Exception):
    """Raised by `complete_checkout_with_business_info` when the user
    has no session in `awaiting_business_info` -- payment hasn't
    succeeded yet, or this session was already consumed into a Store."""


def _create_store_with_unique_slug(*, owner: PlatformUser, store_name: str, **kwargs) -> Store:
    """`create_store` itself is the authoritative uniqueness guard (a DB
    unique constraint, not a pre-check -- see its own docstring); this
    just retries with a random suffix on collision rather than
    surfacing "that name is taken" to a merchant who never typed a slug
    at all in this flow (business info collects a company NAME, not an
    address/slug -- unlike the retired onboarding wizard)."""
    base_slug = slugify(store_name)[:55] or "store"
    slug = base_slug
    last_error: Exception | None = None
    for _ in range(5):
        try:
            return create_store(owner=owner, name=store_name, slug=slug, **kwargs)
        except (IntegrityError, StoreSlugReservedError) as exc:
            last_error = exc
            slug = f"{base_slug}-{secrets.token_hex(3)}"
    raise last_error  # pragma: no cover -- practically unreachable (2^24 suffixes)


def complete_checkout_with_business_info(
    *,
    user: PlatformUser,
    store_name: str,
    business_category: str,
    contact_phone: str,
    logo=None,
) -> Store:
    """The ONLY place this checkout journey actually produces a real
    Store: requires a session already in `awaiting_business_info` (a
    successful demo payment happened), forwards its `theme_preset_id`
    to `create_store`, and marks the session `completed` + `consumed_at`
    so it can never be reused to create a second store. `contact_email`
    is never taken from the request -- always the authenticated user's
    own verified account email, same "never trust client-supplied
    identity" posture as price being server-derived in
    `select_plan_for_checkout_session`."""
    with transaction.atomic():
        session = (
            SubscriptionCheckoutSession.objects.select_for_update()
            .filter(
                user=user,
                checkout_status=(SubscriptionCheckoutSession.CheckoutStatus.AWAITING_BUSINESS_INFO),
            )
            .first()
        )
        if session is None:
            raise CheckoutNotAwaitingBusinessInfoError(
                "No checkout session awaiting business info -- complete payment first."
            )

        store = _create_store_with_unique_slug(
            owner=user,
            store_name=store_name,
            theme_preset_id=session.theme_preset_id,
            contact_email=user.email,
            contact_phone=contact_phone,
            business_category=business_category,
            logo=logo,
        )

        session.checkout_status = SubscriptionCheckoutSession.CheckoutStatus.COMPLETED
        session.provisioning_status = SubscriptionCheckoutSession.ProvisioningStatus.PROVISIONED
        session.store_name_draft = store_name
        session.store_slug_draft = store.slug
        session.business_info_draft = {
            "business_category": business_category,
            "contact_phone": contact_phone,
        }
        session.consumed_at = timezone.now()
        session.save(
            update_fields=[
                "checkout_status",
                "provisioning_status",
                "store_name_draft",
                "store_slug_draft",
                "business_info_draft",
                "consumed_at",
                "updated_at",
            ]
        )
        return store
