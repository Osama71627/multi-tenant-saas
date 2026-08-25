"""
Every privileged, cross-tenant query in this project lives here and
ONLY here -- the approved Phase 14 constraint against a generic
`bypass_rls()`/`run_as_platform()` escape hatch other apps could import.
Every function below is explicit about what it does and uses the
`platform` DB alias (`app_platform_admin`, BYPASSRLS + narrow GRANTs --
see apps/platform_admin/privileges.py) directly and visibly.

Plan/PlanVersion invariants (Phase 10, docs/PHASE_10_REPORT.md) are
preserved on purpose: `publish_plan_version` always creates a NEW
PlanVersion row, never mutates an existing one's terms (price/currency/
features/quotas) -- the only existing-row UPDATE is flipping the
previous version's `is_current` to False in the same transaction, exact
same shape as `apps.subscriptions.management.commands.publish_plan_version`
(the pre-Phase-14 migrator-only tool this supersedes for live admin use).

Every mutation here writes exactly one `AuditLog` row in the same
`transaction.atomic(using="platform")` block as the mutation itself.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts import encryption as accounts_encryption
from apps.accounts import mfa as accounts_mfa
from apps.accounts.models import MfaRecoveryCode, MfaTotpDevice, PlatformUser
from apps.orders.models import Order
from apps.platform_admin.models import AuditLog
from apps.stores.models import Store
from apps.subscriptions import services as subscriptions_services
from apps.subscriptions.models import (
    Plan,
    PlanVersion,
    PlanVersionFeature,
    PlanVersionQuota,
    Subscription,
)

_ANALYTICS_TIME_SERIES_DAYS = 30

_DB = "platform"


def _write_audit_log(
    *,
    actor: PlatformUser,
    action: str,
    target_type: str,
    target_id: UUID,
    store_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog.objects.using(_DB).create(
        actor_user_id=actor.id,
        actor_email=actor.email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        store_id=store_id,
        metadata=metadata or {},
    )


# --------------------------------------------------------------------------
# Stores
# --------------------------------------------------------------------------


def list_stores(*, status: str | None = None) -> QuerySet[Store]:
    qs = Store.objects.using(_DB).all().order_by("name")
    if status:
        qs = qs.filter(status=status)
    return qs


def get_store(store_id: UUID) -> Store:
    return Store.objects.using(_DB).get(id=store_id)


def suspend_store(*, actor: PlatformUser, store: Store, reason: str = "") -> Store:
    with transaction.atomic(using=_DB):
        store.status = Store.Status.SUSPENDED
        store.save(using=_DB, update_fields=["status", "updated_at"])
        _write_audit_log(
            actor=actor,
            action="store.suspend",
            target_type="store",
            target_id=store.id,
            store_id=store.id,
            metadata={"reason": reason} if reason else {},
        )
    return store


def activate_store(*, actor: PlatformUser, store: Store) -> Store:
    with transaction.atomic(using=_DB):
        store.status = Store.Status.ACTIVE
        store.save(using=_DB, update_fields=["status", "updated_at"])
        _write_audit_log(
            actor=actor,
            action="store.activate",
            target_type="store",
            target_id=store.id,
            store_id=store.id,
        )
    return store


# --------------------------------------------------------------------------
# Plans / PlanVersions
# --------------------------------------------------------------------------


def list_plans() -> QuerySet[Plan]:
    return Plan.objects.using(_DB).all().order_by("code")


def get_plan(plan_id: UUID) -> Plan:
    return Plan.objects.using(_DB).get(id=plan_id)


def list_plan_versions(*, plan: Plan) -> QuerySet[PlanVersion]:
    return PlanVersion.objects.using(_DB).filter(plan=plan).order_by("-version_number")


def create_plan(
    *,
    actor: PlatformUser,
    code: str,
    name: str,
    is_public: bool = True,
    trial_days: int = 0,
    grace_period_days: int = 3,
) -> Plan:
    """Metadata only -- a brand-new Plan has no PlanVersion yet, so it is
    not usable by any Subscription until `publish_plan_version` is called
    at least once. `is_default_trial` is deliberately not settable here:
    at most one Plan may ever hold it (DB constraint), and changing which
    one is a separate, rarer operation than ordinary plan creation."""
    with transaction.atomic(using=_DB):
        plan = Plan.objects.using(_DB).create(
            code=code,
            name=name,
            is_public=is_public,
            trial_days=trial_days,
            grace_period_days=grace_period_days,
        )
        _write_audit_log(
            actor=actor,
            action="plan.create",
            target_type="plan",
            target_id=plan.id,
            metadata={"code": code, "name": name},
        )
    return plan


def _set_plan_visibility(*, actor: PlatformUser, plan: Plan, is_public: bool, action: str) -> Plan:
    with transaction.atomic(using=_DB):
        plan.is_public = is_public
        plan.save(using=_DB, update_fields=["is_public", "updated_at"])
        _write_audit_log(actor=actor, action=action, target_type="plan", target_id=plan.id)
    return plan


def activate_plan(*, actor: PlatformUser, plan: Plan) -> Plan:
    return _set_plan_visibility(actor=actor, plan=plan, is_public=True, action="plan.activate")


def deactivate_plan(*, actor: PlatformUser, plan: Plan) -> Plan:
    return _set_plan_visibility(actor=actor, plan=plan, is_public=False, action="plan.deactivate")


def publish_plan_version(
    *,
    actor: PlatformUser,
    plan: Plan,
    price_monthly: int,
    price_yearly: int,
    currency: str = "SAR",
    features: dict[str, bool] | None = None,
    quotas: dict[str, int | None] | None = None,
    make_current: bool = True,
) -> PlanVersion:
    """Always a NEW row -- never mutates an existing PlanVersion's terms.
    Same algorithm as `manage.py publish_plan_version`
    (apps/subscriptions/management/commands/publish_plan_version.py),
    the migrator-only precursor this is the reviewed, request-servable
    equivalent of."""
    with transaction.atomic(using=_DB):
        next_number = (
            PlanVersion.objects.using(_DB)
            .filter(plan=plan)
            .order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
            or 0
        ) + 1
        if make_current:
            PlanVersion.objects.using(_DB).filter(plan=plan, is_current=True).update(
                is_current=False
            )
        version = PlanVersion.objects.using(_DB).create(
            plan=plan,
            version_number=next_number,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            currency=currency,
            is_current=make_current,
        )
        for feature_key, enabled in (features or {}).items():
            PlanVersionFeature.objects.using(_DB).create(
                plan_version=version, feature_key=feature_key, enabled=enabled
            )
        for quota_key, limit in (quotas or {}).items():
            PlanVersionQuota.objects.using(_DB).create(
                plan_version=version, quota_key=quota_key, limit=limit
            )
        _write_audit_log(
            actor=actor,
            action="plan_version.publish",
            target_type="plan_version",
            target_id=version.id,
            metadata={
                "plan_code": plan.code,
                "version_number": next_number,
                "is_current": make_current,
            },
        )
    return version


# --------------------------------------------------------------------------
# Subscriptions
# --------------------------------------------------------------------------


def list_subscriptions(*, store_id: UUID | str | None = None) -> QuerySet[Subscription]:
    qs = Subscription.unscoped.using(_DB).select_related("plan_version__plan").all()
    if store_id:
        qs = qs.filter(store_id=store_id)
    return qs.order_by("-created_at")


def get_subscription(subscription_id: UUID) -> Subscription:
    return (
        Subscription.unscoped.using(_DB)
        .select_related("plan_version__plan")
        .get(id=subscription_id)
    )


def activate_subscription(*, actor: PlatformUser, subscription: Subscription) -> Subscription:
    """Reuses the existing, already-tested Subscription FSM transition
    (apps.subscriptions.services.mark_active) -- the instance was fetched
    via `.using("platform")` above, so `.save()` on it (called inside
    that function, with no explicit `using=`) writes through the SAME
    BYPASSRLS connection it was read from -- ordinary, well-documented
    Django behavior (`Model._state.db`), not a new mechanism."""
    with transaction.atomic(using=_DB):
        subscriptions_services.mark_active(subscription=subscription)
        _write_audit_log(
            actor=actor,
            action="subscription.activate",
            target_type="subscription",
            target_id=subscription.id,
            store_id=subscription.store_id,
        )
    return subscription


def cancel_subscription(*, actor: PlatformUser, subscription: Subscription) -> Subscription:
    with transaction.atomic(using=_DB):
        subscriptions_services.cancel_subscription(subscription=subscription)
        _write_audit_log(
            actor=actor,
            action="subscription.cancel",
            target_type="subscription",
            target_id=subscription.id,
            store_id=subscription.store_id,
        )
    return subscription


# --------------------------------------------------------------------------
# Users (read-only in this Phase 14 slice)
# --------------------------------------------------------------------------


def list_users() -> QuerySet[PlatformUser]:
    return PlatformUser.objects.using(_DB).all().order_by("email")


def get_user(user_id: UUID) -> PlatformUser:
    return PlatformUser.objects.using(_DB).get(id=user_id)


def reset_user_mfa(*, actor: PlatformUser, user: PlatformUser) -> None:
    """
    Phase 17 approved constraint: MFA reset/recovery for a platform-staff
    account (e.g. they lost their authenticator device) must be an
    explicit, audited privileged action -- never a self-service bypass.

    Revokes rather than deletes: blanks `confirmed_at` and rotates the
    device's secret to a fresh, unconfirmed one (the old secret -- and
    thus the lost/compromised authenticator entry -- can never verify a
    code again), and marks every still-usable recovery code as used. This
    forces the target through enrollment again on their next login while
    keeping the "never DELETE" posture of every other grant in
    `apps.platform_admin.privileges` (`app_platform_admin` has no DELETE
    privilege on these tables at all -- an UPDATE-only reset is enforced
    at the grant level, not just in this function). The actor reaching
    this endpoint at all already proves THEY completed MFA
    (`IsPlatformStaff` requires the `mfa` token claim), so no separate
    re-auth step is needed here.
    """
    with transaction.atomic(using=_DB):
        MfaTotpDevice.objects.using(_DB).filter(user=user).update(
            confirmed_at=None,
            secret_encrypted=accounts_encryption.encrypt_secret(
                accounts_mfa.generate_totp_secret()
            ),
        )
        MfaRecoveryCode.objects.using(_DB).filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        _write_audit_log(
            actor=actor,
            action="user.mfa_reset",
            target_type="platform_user",
            target_id=user.id,
        )


# --------------------------------------------------------------------------
# Audit logs (read-only from this surface -- no mutation endpoint exists)
# --------------------------------------------------------------------------


def list_audit_logs(
    *,
    target_type: str | None = None,
    target_id: UUID | str | None = None,
    store_id: UUID | str | None = None,
) -> QuerySet[AuditLog]:
    qs = AuditLog.objects.using(_DB).all()
    if target_type:
        qs = qs.filter(target_type=target_type)
    if target_id:
        qs = qs.filter(target_id=target_id)
    if store_id:
        qs = qs.filter(store_id=store_id)
    return qs


# --------------------------------------------------------------------------
# Overview -- real aggregate counts only, no invented/fake metrics.
# --------------------------------------------------------------------------


def overview_metrics() -> dict[str, Any]:
    """Phase 15 note: `orders_total`/`revenue_by_currency`/
    `orders_last_30_days` are read live via the `platform` alias
    (`app_platform_admin`, SELECT-only on `orders_order` --
    apps/platform_admin/privileges.py), the platform-wide counterpart of
    apps.analytics.services.store_overview_metrics's per-store version.
    Same "live aggregation, no rollup table" MVP choice, same reasoning
    (see that module's docstring)."""
    stores = Store.objects.using(_DB)
    subscriptions = Subscription.unscoped.using(_DB)
    orders = Order.unscoped.using(_DB)

    stores_by_status = dict(stores.values_list("status").annotate(count=Count("id")).order_by())
    subscriptions_by_status = dict(
        subscriptions.values_list("status").annotate(count=Count("id")).order_by()
    )
    revenue_by_currency = dict(
        orders.filter(status=Order.Status.CONFIRMED)
        .values_list("currency")
        .annotate(total=Sum("total_amount"))
        .order_by()
    )
    since = timezone.now() - timedelta(days=_ANALYTICS_TIME_SERIES_DAYS)
    daily_counts = (
        orders.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    return {
        "stores_total": stores.count(),
        "stores_by_status": stores_by_status,
        "plans_total": Plan.objects.using(_DB).count(),
        "subscriptions_by_status": subscriptions_by_status,
        "orders_total": orders.count(),
        "revenue_by_currency": revenue_by_currency,
        "orders_last_30_days": [
            {"date": row["day"].isoformat(), "count": row["count"]} for row in daily_counts
        ],
    }
