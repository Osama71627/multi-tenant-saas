"""
Required test 10 (Phase 11 review round) -- the actual DoD proof.

Per the approved architecture review: "The DoD is not satisfied merely
because enqueue() was called. Prove the rendered email is delivered
through the configured EmailChannel/backend in the integration test."

This drives a REAL storefront checkout over HTTP (cart -> checkout start
-> address/shipping -> complete), confirms the Order through the one
authoritative transition (`apps.orders.services.confirm_order`), lets the
domain event's `on_commit` hook run for real (`captureOnCommitCallbacks`),
and asserts against `django.core.mail.outbox` -- the actual configured
Django email backend (locmem in tests, config/settings/test.py) -- that
an email genuinely landed there, with the real seeded template's content
substituted in, not merely that some dispatch/task call happened.
"""

from __future__ import annotations

import pytest
from django.core import mail

from apps.core.models import EventLog
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import build_confirmed_order, store_db_context

pytestmark = pytest.mark.django_db


def test_order_confirmation_email_is_actually_delivered_via_the_configured_backend(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    mail.outbox.clear()

    order_data = build_confirmed_order(ctx, storefront_client, idempotency_key="e2e-delivery-1")

    # 1. The email genuinely reached the configured backend's outbox --
    # not merely that enqueue()/apply_async() was called.
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [order_data["email"]]
    assert order_data["number"] in sent.subject
    assert "confirmed" in sent.subject.lower()
    assert order_data["number"] in sent.body
    assert ctx["store"].name in sent.body

    # 2. The rendered content matches the real seeded template
    # substitution, not a hand-built string.
    expected_subject = f"Your order {order_data['number']} is confirmed"
    assert sent.subject == expected_subject

    # 3. The durable trail (EventLog + NotificationDispatch) is
    # consistent with what actually got sent.
    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.status == NotificationDispatch.Status.SENT
    assert dispatch.sent_at is not None
    assert dispatch.recipient == order_data["email"]
