"""
Minimal reconciliation (required for Phase 9, approved decision): a
periodic recovery path for `PaymentIntent`s stuck in `processing` past a
threshold. Queries the provider for its authoritative state and applies
the result through `apps.payments.services.apply_payment_transition` --
the SAME function webhook processing uses. There is no second copy of
transition logic here (approved Phase 9 decision: "لا تنشئ transition
logic ثانية خاصة بالreconciliation").

Two-task split mirrors `apps.tenancy.celery`'s own PlatformTask/TenantTask
split: `reconcile_stuck_payment_intents` is a cross-tenant SCAN
(`PlatformTask`, `.unscoped`, read-only), `reconcile_one_payment_intent`
is the actual per-store, RLS-scoped, transition-applying work
(`TenantTask`, dispatched via `dispatch_for_store`).
"""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.payments import services as payment_services
from apps.payments.models import PaymentIntent, PaymentTransaction
from apps.stores.models import Store
from apps.tenancy.celery import PlatformTask, TenantTask, dispatch_for_store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

# Chosen to comfortably exceed any real provider's normal confirmation
# latency (Stripe webhooks typically arrive within seconds) while still
# being short enough that a genuinely stuck payment doesn't leave an
# Order in limbo for long. A reversible implementation detail.
_STUCK_THRESHOLD = timedelta(minutes=30)


@shared_task(base=PlatformTask, name="apps.payments.tasks.reconcile_stuck_payment_intents")
def reconcile_stuck_payment_intents() -> int:
    """
    `PlatformTask` has no ambient tenant (by design -- apps/tenancy/celery.py),
    and `PaymentIntent` is RLS-protected, so a genuine cross-store scan means
    iterating stores one at a time and setting REAL tenant context for each
    (same primitive `TenantTask.__call__` itself uses internally) -- never
    reading via `app_migrator`/`.unscoped` just to skip that, which would
    blur the "migrator is schema-owner only" boundary this project has kept
    clean since Phase 1. `Store` itself is not tenant-owned (its own SELECT
    RLS policy is open), so listing stores needs no context.
    """
    cutoff = timezone.now() - _STUCK_THRESHOLD
    dispatched = 0

    for store in Store.objects.filter(status=Store.Status.ACTIVE):
        with tenant_context(TenantContext(store_id=store.id)):
            apply_tenant_context_to_db(store.id)
            try:
                stuck = PaymentIntent.objects.filter(
                    state=PaymentIntent.State.PROCESSING, updated_at__lt=cutoff
                ).select_related("provider_config")
                for intent in stuck:
                    if not intent.provider_config.is_enabled:
                        continue
                    # manual_cod has nothing external to poll -- a stuck COD intent is a
                    # merchant task (capture_manual_cod_payment), never an automatic one.
                    provider = payment_services.get_provider_for_config(intent.provider_config)
                    if not provider.capabilities.requires_webhook:
                        continue
                    dispatch_for_store(
                        reconcile_one_payment_intent, store.id, payment_intent_id=str(intent.id)
                    )
                    dispatched += 1
            finally:
                clear_tenant_context_from_db()

    return dispatched


@shared_task(base=TenantTask, name="apps.payments.tasks.reconcile_one_payment_intent")
def reconcile_one_payment_intent(payment_intent_id: str) -> None:
    intent = PaymentIntent.objects.get(id=payment_intent_id)
    if intent.state != PaymentIntent.State.PROCESSING:
        return  # already resolved (e.g. a webhook arrived between scan and dispatch)

    provider = payment_services.get_provider_for_config(intent.provider_config)
    result = provider.check_status(provider_ref=intent.provider_ref)

    target_state = (
        PaymentIntent.State.SUCCEEDED
        if result.outcome == "succeeded"
        else PaymentIntent.State.FAILED
    )
    payment_services.apply_payment_transition(
        payment_intent_id=intent.id,
        target_state=target_state,
        kind=PaymentTransaction.Kind.CAPTURE,
        provider_ref=result.provider_ref,
        amount=result.amount or intent.amount,
        raw_response_redacted=result.raw_response_redacted,
        failure_reason=result.failure_reason,
        retryable=result.retryable,
    )
