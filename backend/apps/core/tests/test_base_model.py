import pytest

from apps.core.models import EventLog
from apps.core.uuid7 import is_uuid7

pytestmark = pytest.mark.django_db


def test_event_log_gets_a_uuid7_primary_key():
    event = EventLog.objects.create(event_type="test.event", payload={"a": 1})
    assert is_uuid7(event.id)


def test_event_log_timestamps_auto_populate():
    event = EventLog.objects.create(event_type="test.event")
    assert event.created_at is not None
    assert event.updated_at is not None


def test_event_log_orders_newest_first():
    first = EventLog.objects.create(event_type="first")
    second = EventLog.objects.create(event_type="second")
    assert list(EventLog.objects.values_list("event_type", flat=True)) == ["second", "first"]
    assert first.id != second.id
