"""
Small, cheap unit tests for defensive guards that the main flow never
exercises: a task looked up by an id that no longer exists, an EventLog
with no store_id (platform-level events, not a per-tenant one), and
EmailChannel's own empty-recipient guard (process_committed_event never
calls it with one -- Order.email is a required field -- but the channel
guards it anyway, and that guard deserves direct coverage).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.core.models import EventLog
from apps.notifications import tasks
from apps.notifications.channels.base import PermanentSendError
from apps.notifications.channels.email import EmailChannel

pytestmark = pytest.mark.django_db


def test_process_domain_event_is_a_no_op_for_an_unknown_event_id():
    tasks.process_domain_event(event_id="01a02db0-0000-7000-8000-000000000000")  # no raise


def test_process_domain_event_is_a_no_op_for_a_platform_level_event():
    # EventLog is deliberately NOT tenant-scoped/RLS -- a platform-level
    # event (store_id=None) is valid, just not one apps.notifications
    # attempts to process for a tenant.
    event = EventLog.objects.create(store_id=None, event_type="order.confirmed", payload={})
    tasks.process_domain_event(event_id=str(event.id))  # no raise, no tenant context needed


def test_email_channel_rejects_an_empty_recipient():
    with pytest.raises(PermanentSendError):
        EmailChannel().send(recipient="", subject="x", body="y")


def test_recovery_sweep_survives_one_stores_discovery_query_failing(variant_in_store):
    """One store's anti-join query blowing up (e.g. a transient DB blip)
    must not starve every other store until the next scheduled sweep --
    the exception is caught, logged, and the sweep moves on cleanly
    rather than propagating out of the task."""
    store = variant_in_store["store"]
    EventLog.objects.create(store_id=store.id, event_type="order.confirmed", payload={})

    with patch(
        "apps.notifications.models.NotificationDispatch.objects.filter",
        side_effect=RuntimeError("simulated DB blip"),
    ):
        processed = tasks.recover_unprocessed_domain_events()  # no raise
    assert processed == 0
