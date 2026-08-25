"""
Cheap unit coverage for `process_committed_event`'s early-return guards
-- none of these are reachable through the real checkout->confirm flow
(the only event type ever emitted today is "order.confirmed" with a
real aggregate_id pointing at a real Order), but they're real defensive
code (a future second event type, a malformed payload, an Order deleted
out from under a still-committed event) and deserve direct coverage
rather than being silently unreachable.
"""

from __future__ import annotations

import pytest

from apps.core.models import EventLog
from apps.core.uuid7 import uuid7
from apps.notifications import services
from apps.notifications.tests.conftest import store_db_context

pytestmark = pytest.mark.django_db


def test_ignores_an_unrelated_event_type():
    event = EventLog(event_type="payment.captured", payload={"aggregate_id": str(uuid7())})
    services.process_committed_event(event=event)  # no raise, silently ignored


def test_ignores_an_order_confirmed_event_with_no_aggregate_id():
    event = EventLog(event_type="order.confirmed", payload={})
    services.process_committed_event(event=event)  # no raise, nothing to dispatch for


def test_no_op_when_the_referenced_order_is_not_visible(variant_in_store):
    # A real tenant context, but an aggregate_id that doesn't exist under
    # it -- the same code path a genuinely-deleted/inaccessible Order
    # would take.
    ctx = variant_in_store
    event = EventLog(event_type="order.confirmed", payload={"aggregate_id": str(uuid7())})
    with store_db_context(ctx["store"]):
        services.process_committed_event(event=event)  # DoesNotExist caught, no raise
