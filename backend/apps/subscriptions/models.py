"""
Phase 10 -- Subscriptions. Full decision record in docs/PHASE_10_REPORT.md;
summary of the load-bearing ones:

1. `Plan`/`PlanVersion`/`PlanVersionFeature`/`PlanVersionQuota` are
   platform-global (no `store_id`) -- approved architecture decision 1.
   RLS is enabled with only an open `SELECT` policy
   (`apps.tenancy.rls.global_readonly_policy_sql`); `app_user` has no
   INSERT/UPDATE/DELETE policy on these tables, so ordinary application
   traffic cannot write to them even though it holds a blanket
   table-level GRANT (apps/tenancy/privileges.py) -- RLS is the actual
   boundary. Writes happen only via `app_migrator` (migrations/fixtures).

2. Plan terms are versioned relationally, NOT snapshotted as JSONB on
   `Subscription` (approved architecture decision 3, explicitly
   rejecting the JSONB-snapshot design from the original proposal):
   editing a Plan's terms creates a new `PlanVersion`; existing
   `Subscription`s keep pointing at their current `PlanVersion` (a
   normal FK) until an explicit lifecycle event moves them (renewal or
   an explicit merchant upgrade -- see `apps.subscriptions.services`).
   `PlanVersion`/`PlanVersionFeature`/`PlanVersionQuota` are treated as
   immutable once published: nothing in this app ever updates a
   `PlanVersionQuota.limit` in place -- see
   apps/subscriptions/tests/test_plan_version_isolation.py.

3. `Subscription`/`UsageRecord`/`Invoice` are `TenantOwnedModel`s with
   the STANDARD RLS policy -- no exception for "billing data", per the
   explicit instruction not to extend `apps.core.EventLog`'s RLS-exempt
   precedent to subscription/billing data.

4. `Subscription.status`, `Store.status` (see apps/stores/models.py),
   and an entitlement check's result are three deliberately separate
   concepts (approved decision, section 11 of the proposal) -- a quota
   breach never touches either status field; it only rejects the one
   write that would have crossed the limit.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, TimeStampedModel
from apps.tenancy.models import TenantOwnedModel


class Plan(BaseModel, TimeStampedModel):
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    is_public = models.BooleanField(default=True)
    trial_days = models.PositiveIntegerField(default=0)
    # Configurable policy, deliberately NOT hard-coded into the
    # Subscription FSM (apps/subscriptions/services.py) -- how long a
    # `past_due` Subscription is tolerated before its Store becomes
    # `read_only`. docs/ARCHITECTURE.md section 11 only says "قابل
    # للضبط" (configurable), no concrete number, so this field IS that
    # knob, read at decision time, never a literal in the FSM code.
    grace_period_days = models.PositiveIntegerField(default=3)
    # At most one Plan is ever the automatic trial every new Store gets
    # (apps.stores.services.create_store, in the same transaction as
    # Store/StoreDomain/owner StoreMembership -- approved decision 12:
    # no Store may exist without deterministic entitlement state).
    is_default_trial = models.BooleanField(default=False)

    class Meta:
        db_table = "subscriptions_plan"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default_trial"],
                condition=models.Q(is_default_trial=True),
                name="uniq_default_trial_plan",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.code


class PlanVersion(BaseModel, TimeStampedModel):
    plan = models.ForeignKey(
        "subscriptions.Plan", on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    price_monthly = models.PositiveIntegerField()  # minor units, matches Order/PaymentIntent
    price_yearly = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    # The version a new subscription/renewal moves to when no explicit
    # version is requested -- see apps.subscriptions.services. Never
    # mutated on an EXISTING version; publishing new terms creates a new
    # PlanVersion row and flips this on the new one, in one transaction.
    is_current = models.BooleanField(default=False)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriptions_planversion"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "version_number"], name="uniq_version_number_per_plan"
            ),
            models.UniqueConstraint(
                fields=["plan"],
                condition=models.Q(is_current=True),
                name="uniq_current_version_per_plan",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.plan_id} v{self.version_number}"


class PlanVersionFeature(BaseModel, TimeStampedModel):
    plan_version = models.ForeignKey(
        "subscriptions.PlanVersion", on_delete=models.CASCADE, related_name="features"
    )
    feature_key = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "subscriptions_planversionfeature"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "feature_key"], name="uniq_feature_per_plan_version"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.feature_key} ({'on' if self.enabled else 'off'})"


class PlanVersionQuota(BaseModel, TimeStampedModel):
    class OveragePolicy(models.TextChoices):
        BLOCK = "block", "Block"

    plan_version = models.ForeignKey(
        "subscriptions.PlanVersion", on_delete=models.CASCADE, related_name="quotas"
    )
    quota_key = models.CharField(max_length=64)
    # NULL = unlimited. A quota_key with no row at all (e.g. "storage_mb",
    # for which no feature exists yet to measure usage) is equally
    # unenforced -- apps.subscriptions.entitlements.check_quota treats
    # "no matching row" and "row with limit=NULL" the same way.
    limit = models.PositiveIntegerField(null=True, blank=True)
    overage_policy = models.CharField(
        max_length=16, choices=OveragePolicy.choices, default=OveragePolicy.BLOCK
    )

    class Meta:
        db_table = "subscriptions_planversionquota"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "quota_key"], name="uniq_quota_per_plan_version"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.quota_key} <= {self.limit}"


class Subscription(TenantOwnedModel):
    """One row per store, for the store's entire lifetime -- plan changes
    move `plan_version` on this SAME row (see apps.subscriptions.services);
    `Invoice` is the append-only ledger, not this table."""

    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    class BillingInterval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    plan_version = models.ForeignKey(
        "subscriptions.PlanVersion", on_delete=models.PROTECT, related_name="subscriptions"
    )
    # Set by `apps.subscriptions.services.schedule_downgrade` -- applied at
    # `current_period_end` by the rollover task, never immediately
    # (approved architecture decision 4). NULL means no downgrade pending.
    scheduled_plan_version = models.ForeignKey(
        "subscriptions.PlanVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scheduled_subscriptions",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIALING)
    billing_interval = models.CharField(
        max_length=8, choices=BillingInterval.choices, default=BillingInterval.MONTHLY
    )
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    # Set the moment `status` becomes `past_due`; cleared the moment it
    # leaves `past_due`. The period-rollover sweep
    # (apps.subscriptions.tasks) reads `plan_version.plan.grace_period_days`
    # against THIS to decide when the Store becomes `read_only`.
    past_due_since = models.DateTimeField(null=True, blank=True)
    cancel_at = models.DateTimeField(null=True, blank=True)
    # Inert this phase (no platform billing-provider integration is built
    # -- deferred, see docs/PHASE_10_REPORT.md scope-interpretation note).
    provider_ref = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "subscriptions_subscription"
        constraints = [
            models.UniqueConstraint(fields=["store"], name="uniq_one_subscription_per_store"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Subscription({self.store_id}, {self.status})"


class UsageRecord(TenantOwnedModel):
    """Durable PostgreSQL counter for quota keys classified as append-only
    safe (currently: `orders_per_period` -- Order rows are immutable once
    created, Phase 8 invariant) -- approved architecture decision 5/9.
    Locked via `select_for_update()` inside the same transaction as the
    usage-increasing mutation, same discipline as
    `apps.orders.models.OrderNumberSequence`. A closed period's row is
    never updated again once a new period's row exists."""

    quota_key = models.CharField(max_length=64)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    used = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "subscriptions_usagerecord"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "quota_key", "period_start", "period_end"],
                name="uniq_usage_record_per_period",
            ),
        ]
        indexes = [models.Index(fields=["store", "quota_key", "period_end"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.quota_key}: {self.used} ({self.period_start}..{self.period_end})"


class SubscriptionCheckoutSession(BaseModel, TimeStampedModel):
    """
    Phase D ("product vision reset" -- paid-plan onboarding). Holds the
    theme + plan a visitor picked BEFORE any Store exists, so the
    choice survives a refresh, a logout/login, or a failed/retried
    payment (Phase E). Deliberately NOT a `TenantOwnedModel`: there is
    no store yet at this point in the journey, and this is scoped by
    `user`, not by tenant -- same shape as `apps.accounts.PlatformUser`
    itself (plain `BaseModel`, no RLS; ownership enforced at the view
    layer via `.filter(user=request.user)`/`get_object_or_404(...,
    user=...)`, not a database policy). `app_user` gets normal
    SELECT/INSERT/UPDATE/DELETE on this table automatically
    (apps/tenancy/privileges.py's blanket grant), same as every other
    app_user-writable table in this project.

    `theme_preset_id` is a bare UUIDField, NOT a real ForeignKey to
    `apps.themes.models.ThemePreset` -- `apps.subscriptions` may not
    import `apps.themes` at all (see pyproject.toml's "Layering:
    subscriptions does not depend on catalog" contract, which lists
    `apps.themes` among the forbidden modules). This mirrors the
    EXACT existing precedent for the same cross-layer situation:
    `apps.stores.services.create_store(theme_preset_id=...)` also
    accepts it as an opaque value with no local validation, delegating
    entirely to `apps.themes.services.resolve_theme_preset` at the
    point that actually matters (real store provisioning, Phase G).
    The same is true here: an invalid id simply won't resolve to
    anything the frontend can render, and would be caught for real by
    Phase G's `create_store` call later -- no separate validation
    layer is invented here for a value nothing yet acts on.
    """

    class CheckoutStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY_FOR_PAYMENT = "ready_for_payment", "Ready for payment"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"
        EXPIRED = "expired", "Expired"

    class PaymentStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    class ProvisioningStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        PENDING = "pending", "Pending"
        PROVISIONING = "provisioning", "Provisioning"
        PROVISIONED = "provisioned", "Provisioned"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        "accounts.PlatformUser",
        on_delete=models.CASCADE,
        related_name="subscription_checkout_sessions",
    )
    theme_preset_id = models.UUIDField(null=True, blank=True)
    plan_version = models.ForeignKey(
        "subscriptions.PlanVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="checkout_sessions",
    )
    checkout_status = models.CharField(
        max_length=20, choices=CheckoutStatus.choices, default=CheckoutStatus.DRAFT
    )
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.NOT_STARTED
    )
    provisioning_status = models.CharField(
        max_length=16, choices=ProvisioningStatus.choices, default=ProvisioningStatus.NOT_STARTED
    )
    # Phase F/G fields -- unused (always null/blank) until those phases
    # exist, modeled now so this table doesn't need a second migration
    # the moment they land.
    business_info_draft = models.JSONField(null=True, blank=True)
    store_name_draft = models.CharField(max_length=255, blank=True, default="")
    store_slug_draft = models.SlugField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscriptions_subscriptioncheckoutsession"
        constraints = [
            # At most one ACTIVE (non-terminal) session per user -- a
            # user picking a different theme/plan while they already
            # have a draft updates that SAME row (apps.subscriptions.
            # services.start_or_update_checkout_session), never creates
            # a second one. Mirrors uniq_one_subscription_per_store's
            # "no Store may exist with no deterministic state" spirit,
            # applied one layer earlier in the journey.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(checkout_status__in=["draft", "ready_for_payment"]),
                name="uniq_active_checkout_session_per_user",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"SubscriptionCheckoutSession({self.user_id}, {self.checkout_status})"


class Invoice(TenantOwnedModel):
    """SaaS-billing document -- merchant -> platform money, strictly
    separate from `apps.payments` (storefront customer -> merchant money,
    approved architecture decision 13). `amount`/`currency`/`plan_version`
    are a SNAPSHOT taken at issuance, same discipline as every financial
    snapshot in this project since Phase 8 -- never re-read live from a
    `PlanVersion` that may since have been superseded."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    subscription = models.ForeignKey(
        "subscriptions.Subscription", on_delete=models.PROTECT, related_name="invoices"
    )
    plan_version = models.ForeignKey(
        "subscriptions.PlanVersion", on_delete=models.PROTECT, related_name="invoices"
    )
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Inert this phase, same reasoning as Subscription.provider_ref.
    provider_ref = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "subscriptions_invoice"
        indexes = [models.Index(fields=["store", "status"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Invoice({self.id}, {self.status}, {self.amount} {self.currency})"
