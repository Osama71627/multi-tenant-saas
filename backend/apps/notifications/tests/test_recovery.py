"""
Required test 5 (Phase 11 review round): the post-commit failure gap.
Simulates the crash window `emit_domain_event` can't fully close on its
own (DB commit succeeds, process dies before the `on_commit` callback
actually runs) by creating the `EventLog` row directly -- exactly what's
durably on disk in that scenario -- with NO corresponding
`NotificationDispatch`, then proving `recover_unprocessed_domain_events`
finds and processes it.
"""

from __future__ import annotations

import pytest
from django.core import mail

from apps.core.models import EventLog
from apps.notifications import tasks
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
)
from apps.orders.models import Order
from apps.orders.services import confirm_order

pytestmark = pytest.mark.django_db


def _pending_confirmed_order_with_no_dispatch(ctx, storefront_client, idempotency_key: str):
    """Confirms an Order via `apps.orders.services.confirm_order` DIRECTLY
    (bypassing `apps.core.events.emit_domain_event`'s on_commit hook
    entirely -- the durable EventLog row is written straight, exactly
    what's on disk after a real "committed but never enqueued" crash)."""
    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    complete_address_and_shipping(storefront_client, method["id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=idempotency_key,
    )
    assert response.status_code == 201, response.data
    order_id = response.data["id"]

    with store_db_context(ctx["store"]):
        from django.db import transaction

        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            confirm_order(order=order)  # writes EventLog + schedules on_commit, never captured/run
    return response.data


def test_recovery_sweep_processes_a_committed_event_with_no_dispatch_yet(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    mail.outbox.clear()

    order_data = _pending_confirmed_order_with_no_dispatch(
        ctx, storefront_client, idempotency_key="recovery-1"
    )

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        assert not NotificationDispatch.objects.filter(event=event).exists()  # the gap, simulated

    processed = tasks.recover_unprocessed_domain_events()
    assert processed >= 1

    with store_db_context(ctx["store"]):
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.status == NotificationDispatch.Status.SENT
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [order_data["email"]]


def test_recovery_sweep_is_a_no_op_for_an_already_sent_dispatch(
    variant_in_store, storefront_client
):
    """Idempotent: running recovery again after a real (non-gap) send
    must not create a second dispatch or send a second email."""
    ctx = variant_in_store
    from apps.notifications.tests.conftest import build_confirmed_order

    mail.outbox.clear()
    order_data = build_confirmed_order(ctx, storefront_client, idempotency_key="recovery-noop-1")

    tasks.recover_unprocessed_domain_events()
    tasks.recover_unprocessed_domain_events()

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        dispatches = list(
            NotificationDispatch.objects.filter(event=event, notification_type="order_confirmation")
        )
    assert len(dispatches) == 1
    assert dispatches[0].status == NotificationDispatch.Status.SENT
    assert len(mail.outbox) == 1  # not re-sent by either recovery run
