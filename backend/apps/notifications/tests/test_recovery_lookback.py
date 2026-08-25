"""
Phase 11 review round 2, required regression tests: the recovery sweep
used to gate eligibility on `EventLog.created_at >= now() - LOOKBACK`
alone -- a never-dispatched event older than the configured lookback
would be permanently invisible to recovery forever, violating "a
committed notification-eligible domain event must not be permanently
lost merely because the process crashed between DB commit and Celery
publish." Fixed shape (apps/notifications/tasks.py::
recover_unprocessed_domain_events): a per-store, RLS-scoped anti-join
against `NotificationDispatch` -- age plays no part in eligibility.
`NOTIFICATION_RECOVERY_LOOKBACK_HOURS` now only flags a stale find for
an operator-visibility log line, never gates processing.

`created_at` is `auto_now_add` -- forced into the past here via a raw
`.update()` after creation (bypasses `auto_now_add`, which only applies
at INSERT time through `save()`), the only way to simulate "this event
has been sitting uncollected for a very long time" without actually
waiting.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.conf import settings
from django.core import mail
from django.utils import timezone

from apps.core.models import EventLog
from apps.notifications import tasks
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import build_confirmed_order, store_db_context
from apps.notifications.tests.test_recovery import _pending_confirmed_order_with_no_dispatch

pytestmark = pytest.mark.django_db


def _age_event_past_the_lookback(store, order_id: str) -> None:
    stale_at = timezone.now() - timedelta(hours=settings.NOTIFICATION_RECOVERY_LOOKBACK_HOURS + 24)
    with store_db_context(store):
        EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_id
        ).update(created_at=stale_at)


def test_an_old_never_dispatched_event_is_still_recovered(variant_in_store, storefront_client):
    """Required regression 1: eligible EventLog older than the configured
    lookback but with no NotificationDispatch is still recoverable."""
    ctx = variant_in_store
    mail.outbox.clear()

    order_data = _pending_confirmed_order_with_no_dispatch(
        ctx, storefront_client, idempotency_key="lookback-old-orphan-1"
    )
    _age_event_past_the_lookback(ctx["store"], order_data["id"])

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        age = timezone.now() - event.created_at
        lookback = timedelta(hours=settings.NOTIFICATION_RECOVERY_LOOKBACK_HOURS)
        assert age > lookback  # genuinely stale, not just barely outside the window
        assert not NotificationDispatch.objects.filter(event=event).exists()

    processed = tasks.recover_unprocessed_domain_events()
    assert processed >= 1

    with store_db_context(ctx["store"]):
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.status == NotificationDispatch.Status.SENT
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [order_data["email"]]


def test_an_old_event_with_a_terminal_dispatch_is_excluded_not_just_a_no_op(
    variant_in_store, storefront_client
):
    """Required regression 2: an old EventLog that already has a
    terminal/successful NotificationDispatch is a no-op -- proven at the
    STRONGER level of "excluded by the anti-join entirely" (processed
    count is 0 for this store), not merely "reprocessed harmlessly"."""
    ctx = variant_in_store
    mail.outbox.clear()

    order_data = build_confirmed_order(
        ctx, storefront_client, idempotency_key="lookback-old-sent-1"
    )
    _age_event_past_the_lookback(ctx["store"], order_data["id"])
    mail.outbox.clear()  # the real send from build_confirmed_order already happened

    processed = tasks.recover_unprocessed_domain_events()
    # the anti-join found nothing eligible for this store -- excluded, not re-run
    assert processed == 0

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        dispatches = list(
            NotificationDispatch.objects.filter(event=event, notification_type="order_confirmation")
        )
    assert len(dispatches) == 1
    assert dispatches[0].status == NotificationDispatch.Status.SENT
    assert len(mail.outbox) == 0  # not re-sent


def test_repeated_recovery_of_an_old_orphan_never_creates_a_second_dispatch(
    variant_in_store, storefront_client
):
    """Required regression 3: running recovery repeatedly never creates a
    second logical dispatch -- for the old-orphan case specifically, not
    just the already-covered recent-event case
    (test_recovery.py::test_recovery_sweep_is_a_no_op_for_an_already_sent_dispatch)."""
    ctx = variant_in_store
    mail.outbox.clear()

    order_data = _pending_confirmed_order_with_no_dispatch(
        ctx, storefront_client, idempotency_key="lookback-old-repeat-1"
    )
    _age_event_past_the_lookback(ctx["store"], order_data["id"])

    first = tasks.recover_unprocessed_domain_events()
    second = tasks.recover_unprocessed_domain_events()
    third = tasks.recover_unprocessed_domain_events()

    assert first >= 1
    assert second == 0  # already terminal after the first run -- excluded on every subsequent sweep
    assert third == 0

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        dispatches = list(
            NotificationDispatch.objects.filter(event=event, notification_type="order_confirmation")
        )
    assert len(dispatches) == 1
    assert dispatches[0].status == NotificationDispatch.Status.SENT
    assert len(mail.outbox) == 1  # exactly one email across all 3 sweep runs
