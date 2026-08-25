"""
Minimal reconciliation (required for Phase 9): the recovery path for
`PaymentIntent`s stuck in `processing`. `CELERY_TASK_ALWAYS_EAGER=True`
(config/settings/test.py) runs tasks synchronously in-process -- no
broker needed, same as every other Celery-touching test in this project
(apps/stores/tests/test_celery_tenant_context.py).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.payments import tasks as payment_tasks
from apps.payments.tests.conftest import create_order, enable_provider, store_db_context

pytestmark = pytest.mark.django_db


def _make_stuck_intent(ctx, order_data, *, provider_key="mock", age=timedelta(hours=1)):
    from apps.orders.models import Order
    from apps.payments.models import PaymentIntent, StoreProviderConfig

    with store_db_context(ctx["store"]):
        config = StoreProviderConfig.objects.get(provider_key=provider_key)
        order = Order.objects.get(id=order_data["id"])
        intent = PaymentIntent.objects.create(
            store=ctx["store"],
            order=order,
            provider_config=config,
            amount=order.total_amount,
            currency=order.currency,
            state="processing",
            provider_ref=f"{provider_key}_pi_stuck",
            idempotency_key="stuck-key",
        )
        PaymentIntent.objects.filter(id=intent.id).update(updated_at=timezone.now() - age)
        return intent


def test_reconcile_scan_dispatches_only_stuck_intents(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)
    stuck = _make_stuck_intent(ctx, order, age=timedelta(hours=1))

    dispatched = payment_tasks.reconcile_stuck_payment_intents()
    assert dispatched == 1

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentIntent

        resolved = PaymentIntent.objects.get(id=stuck.id)
        # MockProvider.check_status's deterministic default is a non-retryable failure.
        assert resolved.state == "failed"


def test_reconcile_scan_ignores_recently_updated_intents(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)
    fresh = _make_stuck_intent(ctx, order, age=timedelta(minutes=1))

    dispatched = payment_tasks.reconcile_stuck_payment_intents()
    assert dispatched == 0

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentIntent

        assert PaymentIntent.objects.get(id=fresh.id).state == "processing"


def test_reconcile_scan_skips_intents_for_a_disabled_provider(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)
    _make_stuck_intent(ctx, order, age=timedelta(hours=1))

    from apps.payments.models import StoreProviderConfig

    with store_db_context(ctx["store"]):
        StoreProviderConfig.objects.filter(provider_key="mock").update(is_enabled=False)

    dispatched = payment_tasks.reconcile_stuck_payment_intents()
    assert dispatched == 0


def test_reconcile_scan_skips_manual_cod_intents(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    _make_stuck_intent(ctx, order, provider_key="manual_cod", age=timedelta(hours=1))

    dispatched = payment_tasks.reconcile_stuck_payment_intents()
    assert dispatched == 0  # manual_cod has nothing external to poll


def test_reconcile_resolves_a_stuck_intent_and_cancels_the_order(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)
    _make_stuck_intent(ctx, order, age=timedelta(hours=1))

    payment_tasks.reconcile_stuck_payment_intents()

    with store_db_context(ctx["store"]):
        from apps.orders.models import Order

        assert Order.objects.get(id=order["id"]).status == Order.Status.CANCELLED


def test_reconcile_one_payment_intent_is_a_no_op_if_already_resolved(
    variant_in_store, storefront_client
):
    """Guards against a webhook resolving the intent between scan and dispatch."""
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)
    stuck = _make_stuck_intent(ctx, order, age=timedelta(hours=1))

    with store_db_context(ctx["store"]):
        from apps.payments import services as payment_services
        from apps.payments.models import PaymentTransaction

        payment_services.apply_payment_transition(
            payment_intent_id=stuck.id,
            target_state="succeeded",
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref=stuck.provider_ref,
            amount=stuck.amount,
        )

    from apps.tenancy.celery import dispatch_for_store

    dispatch_for_store(
        payment_tasks.reconcile_one_payment_intent, ctx["store"].id, payment_intent_id=str(stuck.id)
    )

    with store_db_context(ctx["store"]):
        from apps.orders.models import Order
        from apps.payments.models import PaymentIntent

        assert PaymentIntent.objects.get(id=stuck.id).state == "succeeded"
        assert Order.objects.get(id=order["id"]).status == Order.Status.CONFIRMED
