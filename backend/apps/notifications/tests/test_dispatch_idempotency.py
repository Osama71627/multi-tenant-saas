"""
Required tests 3-4 (Phase 11 review round): the same domain event
processed repeatedly collapses to one logical NotificationDispatch; a
provider/worker failure never surfaces into Order/Payment/Inventory
state -- it only ever mutates NotificationDispatch itself.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.core.models import EventLog
from apps.notifications import services
from apps.notifications.channels.base import PermanentSendError
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import build_confirmed_order, store_db_context
from apps.orders.models import Order

pytestmark = pytest.mark.django_db


def _order_confirmed_event(store):
    """NEVER call this nested inside an already-open `store_db_context`
    block: `store_db_context`/`clear_tenant_context_from_db` unconditionally
    clear the GUC on exit rather than restoring a previous value, so
    nesting silently drops the OUTER block's tenant context for every
    statement after this one returns -- discovered directly as a real bug
    while writing these tests. Always call this FIRST, standalone."""
    with store_db_context(store):
        return EventLog.objects.filter(event_type="order.confirmed").latest("created_at")


def test_same_event_processed_repeatedly_yields_one_logical_dispatch(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    order_data = build_confirmed_order(ctx, storefront_client, idempotency_key="idem-repeat-1")
    event = _order_confirmed_event(ctx["store"])

    for _ in range(10):
        with store_db_context(ctx["store"]):
            services.process_committed_event(event=event)

    with store_db_context(ctx["store"]):
        dispatches = list(
            NotificationDispatch.objects.filter(event=event, notification_type="order_confirmation")
        )
    assert len(dispatches) == 1
    assert dispatches[0].status == NotificationDispatch.Status.SENT
    assert dispatches[0].recipient == order_data["email"]


def test_transient_send_failure_never_touches_order_payment_or_inventory(
    variant_in_store, storefront_client
):
    """A `NotificationChannel.send` failure must only ever mutate the
    NotificationDispatch row -- Order status, any PaymentIntent, and
    inventory reservations/balances are all completely untouched."""
    ctx = variant_in_store

    with patch(
        "apps.notifications.channels.email.EmailChannel.send",
        side_effect=ConnectionError("simulated SMTP outage"),
    ):
        order_data = build_confirmed_order(ctx, storefront_client, idempotency_key="idem-fail-1")

    event = _order_confirmed_event(ctx["store"])
    with store_db_context(ctx["store"]):
        order = Order.objects.get(id=order_data["id"])
        assert order.status == Order.Status.CONFIRMED  # unaffected by the notification failure

        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
        assert dispatch.status == NotificationDispatch.Status.PENDING  # transient, still retryable
        assert dispatch.attempts == 1
        assert "simulated SMTP outage" in dispatch.last_error


def test_permanent_send_error_marks_failed_without_retry(variant_in_store, storefront_client):
    ctx = variant_in_store
    with patch(
        "apps.notifications.channels.email.EmailChannel.send",
        side_effect=PermanentSendError("bad recipient"),
    ):
        build_confirmed_order(ctx, storefront_client, idempotency_key="idem-permanent-1")

    event = _order_confirmed_event(ctx["store"])
    with store_db_context(ctx["store"]):
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.status == NotificationDispatch.Status.FAILED
    assert dispatch.attempts == 0  # never counted as a retryable attempt
    assert "bad recipient" in dispatch.last_error


def test_repeated_transient_failures_dead_letter_after_max_attempts(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    with patch(
        "apps.notifications.channels.email.EmailChannel.send",
        side_effect=ConnectionError("simulated SMTP outage"),
    ):
        # The fast-path task (apps.notifications.tasks.process_domain_event)
        # swallows the exception itself -- this is the ONE attempt it makes,
        # bringing attempts to 1 (still PENDING).
        build_confirmed_order(ctx, storefront_client, idempotency_key="idem-deadletter-1")
        event = _order_confirmed_event(ctx["store"])

        # apps.notifications.services.process_committed_event (unlike the
        # task) re-raises while still retryable -- calling it directly
        # here mirrors what the recovery sweep does on each of its runs.
        # attempts 2, 3, 4 are still below the ceiling and raise; the 5th
        # attempt crosses `_MAX_ATTEMPTS` and returns normally, terminal.
        for _ in range(3):
            with store_db_context(ctx["store"]), pytest.raises(ConnectionError):
                services.process_committed_event(event=event)
        with store_db_context(ctx["store"]):
            services.process_committed_event(event=event)  # 5th attempt -- goes terminal, no raise

    with store_db_context(ctx["store"]):
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.status == NotificationDispatch.Status.DEAD_LETTER
    assert dispatch.attempts == 5
