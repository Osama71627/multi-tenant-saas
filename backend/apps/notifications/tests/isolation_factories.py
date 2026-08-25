"""Registers apps.notifications TenantOwnedModels with the generic isolation test suite."""

from apps.core.models import EventLog
from apps.notifications.models import NotificationDispatch
from apps.tenancy.testing import register


@register(NotificationDispatch)
def _dispatch_factory(store, suffix: str) -> NotificationDispatch:
    event = EventLog.objects.create(
        store_id=store.id, event_type="order.confirmed", payload={"iso-suffix": suffix}
    )
    return NotificationDispatch.objects.create(
        store=store,
        event=event,
        channel=NotificationDispatch.Channel.EMAIL,
        notification_type="order_confirmation",
        recipient=f"{suffix}@example.com",
    )
