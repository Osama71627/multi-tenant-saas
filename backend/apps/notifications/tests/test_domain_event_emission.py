"""
Required tests 1-2 (Phase 11 review round): confirm_order emits exactly
one durable domain event on commit; a rolled-back confirmation commits
neither an event nor a dispatch.
"""

from __future__ import annotations

import pytest
from django.db import transaction

from apps.core.models import EventLog
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    build_confirmed_order,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
)
from apps.orders.models import Order
from apps.orders.services import confirm_order

pytestmark = pytest.mark.django_db


def test_confirm_order_emits_exactly_one_durable_domain_event(variant_in_store, storefront_client):
    ctx = variant_in_store
    order_data = build_confirmed_order(ctx, storefront_client, idempotency_key="event-emit-1")

    with store_db_context(ctx["store"]):
        events = list(
            EventLog.objects.filter(
                event_type="order.confirmed", payload__aggregate_id=order_data["id"]
            )
        )
    assert len(events) == 1
    event = events[0]
    assert event.store_id == ctx["store"].id
    assert event.payload["aggregate_type"] == "order"
    assert event.payload["aggregate_id"] == order_data["id"]
    # Identifiers/audit context only -- no financial snapshot duplicated here.
    assert set(event.payload.keys()) == {"aggregate_type", "aggregate_id", "order_number"}


def test_rolled_back_order_confirmation_commits_no_event_and_no_dispatch(
    variant_in_store, storefront_client
):
    """`confirm_order` emits the event AND registers the on_commit Celery
    nudge INSIDE the same transaction as the status change -- if anything
    else in that same transaction fails afterward and the whole thing
    rolls back, neither the EventLog row nor any notification attempt
    must survive (Django's on_commit hooks only ever fire on an actual
    commit, never on a rollback -- this proves the EventLog side of that
    the same way, at the DB level, not just by trusting Django's docs)."""
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    complete_address_and_shipping(storefront_client, method["id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="event-rollback-1",
    )
    assert response.status_code == 201, response.data
    order_id = response.data["id"]

    class _SimulatedFailureAfterConfirm(Exception):
        pass

    with store_db_context(ctx["store"]):
        with pytest.raises(_SimulatedFailureAfterConfirm):
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order_id)
                confirm_order(order=order)  # emits the event, schedules on_commit
                raise _SimulatedFailureAfterConfirm("something else in this transaction failed")

    with store_db_context(ctx["store"]):
        order_after = Order.objects.get(id=order_id)
        assert order_after.status == Order.Status.PENDING_PAYMENT  # rolled back too
        events = list(
            EventLog.objects.filter(event_type="order.confirmed", payload__aggregate_id=order_id)
        )
        dispatches = list(NotificationDispatch.objects.all())
    assert events == []
    assert dispatches == []
