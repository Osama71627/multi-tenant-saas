"""
`apply_payment_transition` -- the one place that mutates `PaymentIntent.state`
or cascades into Order/inventory (apps/payments/services.py's module docstring).
Real PostgreSQL, real Order created through the actual Phase 8 checkout flow so
what's being proven is the real reservation lifecycle, not a stand-in.
"""

from __future__ import annotations

import pytest

from apps.orders.models import Order, order_reservation_reference
from apps.payments import services
from apps.payments.models import PaymentIntent, PaymentTransaction, StoreProviderConfig
from apps.payments.tests.conftest import create_order, enable_provider, store_db_context

pytestmark = pytest.mark.django_db


def _make_intent(ctx, order_data, *, state="processing") -> PaymentIntent:
    with store_db_context(ctx["store"]):
        config = StoreProviderConfig.objects.get(provider_key="mock")
        order = Order.objects.get(id=order_data["id"])
        return PaymentIntent.objects.create(
            store=ctx["store"],
            order=order,
            provider_config=config,
            amount=order.total_amount,
            currency=order.currency,
            state=state,
            provider_ref="mock_pi_1",
            idempotency_key="test-key",
        )


def test_success_confirms_order_and_fulfills_reservation(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.SUCCEEDED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
        )
        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.CONFIRMED

        from apps.inventory.models import StockReservation

        reservations = StockReservation.objects.filter(
            reference=order_reservation_reference(order.id)
        )
        assert reservations.count() == 1
        assert reservations.first().status == StockReservation.Status.FULFILLED


def test_retryable_failure_leaves_order_pending_and_reservation_active(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.FAILED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
            failure_reason="card_declined",
            retryable=True,
        )
        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.PENDING_PAYMENT

        from apps.inventory.models import StockReservation

        reservations = StockReservation.objects.filter(
            reference=order_reservation_reference(order.id)
        )
        assert reservations.first().status == StockReservation.Status.ACTIVE


def test_non_retryable_failure_cancels_order_and_releases_reservation(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.FAILED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
            failure_reason="fraud_block",
            retryable=False,
        )
        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.CANCELLED

        from apps.inventory.models import StockReservation

        reservations = StockReservation.objects.filter(
            reference=order_reservation_reference(order.id)
        )
        assert reservations.first().status == StockReservation.Status.RELEASED


def test_reapplying_a_terminal_transition_is_a_no_op(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.SUCCEEDED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
        )
        # Re-apply the SAME success again -- must not double-fulfill.
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.SUCCEEDED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
        )
        from apps.inventory.models import StockReservation

        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.CONFIRMED  # unchanged, not double-processed

        reservations = StockReservation.objects.filter(
            reference=order_reservation_reference(order.id)
        )
        assert reservations.count() == 1  # never a second reservation/fulfillment record

        # But a PaymentTransaction audit row IS recorded for the duplicate event.
        assert PaymentTransaction.objects.filter(intent=intent).count() == 2


def test_cancelled_target_state_cancels_the_order_like_a_non_retryable_failure(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.CANCELLED,
            kind=PaymentTransaction.Kind.VOID,
            provider_ref="mock_pi_1",
            amount=intent.amount,
        )
        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.CANCELLED

        from apps.inventory.models import StockReservation

        reservations = StockReservation.objects.filter(
            reference=order_reservation_reference(order.id)
        )
        assert reservations.first().status == StockReservation.Status.RELEASED


def test_an_unexpected_target_state_is_a_no_op(variant_in_store, storefront_client):
    """Defensive guard: `target_state` not in the allowed set for the current
    state (here, "processing" itself is never a valid TARGET, only a starting
    state) is rejected without mutating anything."""
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        result = services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.PROCESSING,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
        )
        assert result.state == PaymentIntent.State.PROCESSING  # unchanged
        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.PENDING_PAYMENT  # untouched


def test_an_unhandled_webhook_event_kind_is_not_treated_as_a_failure(
    variant_in_store, storefront_client
):
    """Regression: an event type a provider sends that we don't act on (e.g. Stripe's
    `payment_intent.created` if a merchant's webhook config forwards every event type)
    must never be silently treated as a payment failure -- found and fixed during
    Phase 9 test-authoring, not a pre-existing production incident."""
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    from apps.payments.providers.base import DomainPaymentEvent
    from apps.payments.services import _apply_domain_event

    with store_db_context(ctx["store"]):
        _apply_domain_event(
            intent=intent,
            domain_event=DomainPaymentEvent(
                external_id="evt_unhandled",
                provider_ref=intent.provider_ref,
                kind="unhandled",
                amount=intent.amount,
                currency=intent.currency,
            ),
        )
        intent.refresh_from_db()
        order = Order.objects.get(id=order_data["id"])
        assert intent.state == PaymentIntent.State.PROCESSING  # untouched
        assert order.status == Order.Status.PENDING_PAYMENT  # untouched


def test_a_failure_event_after_success_is_recorded_but_does_not_regress(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_data = create_order(ctx, storefront_client)
    intent = _make_intent(ctx, order_data)

    with store_db_context(ctx["store"]):
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.SUCCEEDED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
        )
        # An out-of-order failure event arrives after success was already applied.
        services.apply_payment_transition(
            payment_intent_id=intent.id,
            target_state=PaymentIntent.State.FAILED,
            kind=PaymentTransaction.Kind.CAPTURE,
            provider_ref="mock_pi_1",
            amount=intent.amount,
            retryable=False,
        )
        intent.refresh_from_db()
        order = Order.objects.get(id=order_data["id"])
        assert intent.state == PaymentIntent.State.SUCCEEDED  # never regresses
        assert order.status == Order.Status.CONFIRMED
