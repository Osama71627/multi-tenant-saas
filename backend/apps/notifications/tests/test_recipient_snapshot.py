"""
Required test 8 (Phase 11 review round): the order-confirmation
recipient comes from the authoritative `Order.email` snapshot, NOT from
`CheckoutSession.email`/Cart, a new request payload, webhook metadata,
or Payment metadata. `Order.email` is copied from `CheckoutSession.email`
once, at order-creation time (apps/orders/services.py) -- this test
mutates the CheckoutSession's (still-live) email AFTER order creation
but BEFORE the confirmation/dispatch step, proving dispatch resolution
never goes back to re-read it.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.db import transaction
from django.test import TestCase

from apps.core.models import EventLog
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
)
from apps.orders.models import CheckoutSession, Order
from apps.orders.services import confirm_order

pytestmark = pytest.mark.django_db


def test_dispatch_recipient_is_order_email_snapshot_not_live_checkout_session(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    mail.outbox.clear()

    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    complete_address_and_shipping(storefront_client, method["id"])  # sets CheckoutSession.email
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="recipient-snap-1",
    )
    assert response.status_code == 201, response.data
    order_id = response.data["id"]

    with store_db_context(ctx["store"]):
        order = Order.objects.get(id=order_id)
        assert order.email == "shopper@example.com"  # snapshot taken at order-creation time

        # Mutate the still-live CheckoutSession's email BEFORE confirmation --
        # if dispatch resolution ever re-read this instead of Order.email,
        # the recipient below would flip to this value. RLS-scoped to this
        # store already, so this only touches this test's own row.
        CheckoutSession.objects.all().update(email="tampered-checkout-session@example.com")

        with TestCase.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                locked = Order.objects.select_for_update().get(id=order_id)
                confirm_order(order=locked)
        # NOTE: the Celery task just ran synchronously above and clears the
        # tenant GUC on its own exit (apps.tenancy.celery's PlatformTask
        # pattern) -- it does NOT restore this block's context afterward.
        # Querying NotificationDispatch/EventLog further down MUST happen in
        # a fresh `store_db_context` call, never trailing inside this one
        # (the same nested-context pitfall documented in
        # test_dispatch_idempotency.py's `_order_confirmed_event`).

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_id
        ).get()
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )

    assert dispatch.recipient == "shopper@example.com"
    assert dispatch.recipient != "tampered-checkout-session@example.com"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["shopper@example.com"]
