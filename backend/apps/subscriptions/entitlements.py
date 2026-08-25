"""
The single entitlement policy boundary (docs/ARCHITECTURE.md section 11;
approved architecture decision 5). Called from Services, never Views --
so it applies uniformly to the HTTP API and any future batch/Celery path
that reuses the same service functions.

Two independent checks, matching the doc's literal signatures:

    entitlements.require_feature(store=store, feature_key="custom_domain")
    entitlements.check_quota(store=store, quota_key="products", delta=1)

Registry, not a hard dependency: `apps.subscriptions` never imports
`apps.catalog` (or any other domain app) -- a "live-COUNT-derived" quota
(approved decision 6/9, category A: `products`) needs a way to count
CURRENT usage without this app knowing what a Product is. The owning app
registers its own counter from `AppConfig.ready()` (see
apps/catalog/apps.py) -- the same "app registers itself with a lower
layer, never the reverse" shape Django's own admin/signals use.

Explicit limitation (approved architecture decision 10, review round):
this registry proves that EVERY REGISTERED quota-controlled path is
enforced (apps/subscriptions/tests/test_entitlements.py); it cannot prove
that some future write path forgets to call `check_quota` at all -- that
remains a service-layer code-review discipline, same as every other
business rule in this project, not a structural guarantee. Do not
represent this module as closing that gap by itself.
"""

from __future__ import annotations

from collections.abc import Callable

from django.db import transaction

from apps.stores.models import Store
from apps.subscriptions import locks
from apps.subscriptions.models import (
    PlanVersionFeature,
    PlanVersionQuota,
    Subscription,
    UsageRecord,
)

# Quota keys whose authoritative usage is a live `COUNT(*)` against the
# owning app's own table (category A) rather than a maintained
# `UsageRecord` counter (category B). Populated only via
# `register_live_counter`, called from each owning app's `AppConfig.ready()`.
_live_counters: dict[str, Callable[[Store], int]] = {}


class EntitlementError(Exception):
    """Base class for both rejection kinds below -- callers that only
    care "was this rejected" may catch this instead of the two subclasses."""


class FeatureNotEntitledError(EntitlementError):
    def __init__(self, feature_key: str) -> None:
        self.feature_key = feature_key
        super().__init__(f"This store's plan does not include '{feature_key}'.")


class QuotaExceededError(EntitlementError):
    def __init__(self, quota_key: str, *, limit: int) -> None:
        self.quota_key = quota_key
        self.limit = limit
        super().__init__(f"'{quota_key}' quota exceeded (limit={limit}). Upgrade your plan.")


def register_live_counter(quota_key: str, counter: Callable[[Store], int]) -> None:
    """Registers `counter(store) -> int` as the authoritative current usage
    for `quota_key`. Idempotent (safe if `AppConfig.ready()` runs more than
    once, e.g. under the dev autoreloader)."""
    _live_counters[quota_key] = counter


def _current_subscription(store: Store) -> Subscription:
    return Subscription.objects.select_related("plan_version").get(store=store)


def require_feature(*, store: Store, feature_key: str) -> None:
    subscription = _current_subscription(store)
    try:
        feature = PlanVersionFeature.objects.get(
            plan_version=subscription.plan_version, feature_key=feature_key
        )
    except PlanVersionFeature.DoesNotExist:
        raise FeatureNotEntitledError(feature_key) from None
    if not feature.enabled:
        raise FeatureNotEntitledError(feature_key)


def check_quota(*, store: Store, quota_key: str, delta: int = 1) -> None:
    """Must be called inside an open `transaction.atomic()` block that also
    contains the usage-increasing mutation itself -- both the lock/row-lock
    below and the mutation succeed or roll back together.

    A real `if`/`raise` rather than a bare `assert`: `assert` statements
    are stripped entirely under `python -O`, which would silently turn
    this safety net into a no-op in exactly the deployment mode where a
    misuse bug would be hardest to catch.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("entitlements.check_quota must be called inside transaction.atomic()")
    subscription = _current_subscription(store)
    try:
        quota = PlanVersionQuota.objects.get(
            plan_version=subscription.plan_version, quota_key=quota_key
        )
    except PlanVersionQuota.DoesNotExist:
        return  # no quota configured for this key -- unenforced, not unlimited-by-claim
    if quota.limit is None:
        return  # explicitly unlimited

    if quota_key in _live_counters:
        _check_live_count_quota(store=store, quota_key=quota_key, limit=quota.limit, delta=delta)
    else:
        _check_and_increment_usage_record(
            store=store,
            subscription=subscription,
            quota_key=quota_key,
            limit=quota.limit,
            delta=delta,
        )


def _check_live_count_quota(*, store: Store, quota_key: str, limit: int, delta: int) -> None:
    locks.acquire_quota_lock(store.id, quota_key)
    current = _live_counters[quota_key](store)
    if current + delta > limit:
        raise QuotaExceededError(quota_key, limit=limit)


def _check_and_increment_usage_record(
    *, store: Store, subscription: Subscription, quota_key: str, limit: int, delta: int
) -> None:
    record, _created = UsageRecord.objects.select_for_update().get_or_create(
        store=store,
        quota_key=quota_key,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        defaults={"used": 0},
    )
    if record.used + delta > limit:
        raise QuotaExceededError(quota_key, limit=limit)
    record.used += delta
    record.save(update_fields=["used", "updated_at"])


class StoreNotPurchasableError(Exception):
    """Raised when a Store's operational status blocks purchase/write
    activity (approved architecture decision 11: driven by Subscription
    lifecycle via `apps.subscriptions.tasks`, but checked here purely as
    a `Store.status` read -- see that field's own docstring)."""


def require_active_store(*, store: Store) -> None:
    if store.status == Store.Status.READ_ONLY:
        raise StoreNotPurchasableError(
            "This store is read-only pending a subscription/plan action."
        )


__all__ = [
    "EntitlementError",
    "FeatureNotEntitledError",
    "QuotaExceededError",
    "StoreNotPurchasableError",
    "check_quota",
    "register_live_counter",
    "require_active_store",
    "require_feature",
]
