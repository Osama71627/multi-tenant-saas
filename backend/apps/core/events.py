"""
Domain Event emission -- the ONLY sanctioned way a write-side Service
triggers something outside its own app, per docs/ARCHITECTURE.md line
107/108: Django Signals are forbidden in critical paths (order, payment,
inventory) -- "تُستخدم فقط للأمور الجانبية (audit, cache invalidation)"
-- and "كل عملية كتابة تُصدر Domain Event يُسجَّل في core.EventLog
ويُرسل للـ Celery عند الحاجة" (every write emits a Domain Event, recorded
in core.EventLog, sent to Celery when needed). This module is that literal
mechanism, not a signal/observer-pattern substitute for one.

Two deliberately separate concerns, per Phase 11's approved review round:

1. DURABLE RECORD -- an `EventLog` row, written inside the CALLER's own
   open `transaction.atomic()` block, so a rolled-back transaction never
   leaves a committed event behind. This is the actual "did this happen"
   source of truth for any downstream consumer.

2. ASYNC FAN-OUT -- `transaction.on_commit()` schedules a Celery task
   PER CONSUMER, resolved by STRING NAME from
   `settings.DOMAIN_EVENT_CONSUMER_TASKS` (a plain data mapping, not a
   Python import) -- e.g. `apps.notifications.tasks.process_domain_event`.
   This is a fast-path nudge only, never the correctness guarantee: if
   the process crashes between the DB commit and this callback actually
   running, the event is still durably committed and simply unprocessed
   until a consumer's own recovery sweep finds it (see
   apps/notifications/tasks.py's `recover_unprocessed_domain_events`).

`apps.core` never imports a domain app to make this work -- only the
concrete Celery app object (`config.celery_app`, project infrastructure,
not a domain app) and a STRING task name resolved from
`settings.DOMAIN_EVENT_CONSUMER_TASKS`. This is what lets a producer
(apps.orders today) trigger a consumer (apps.notifications) without
either one importing the other, satisfying docs/ARCHITECTURE.md section
3's "reverse connection via Domain Events only" rule for the actual
notification-trigger case.

Deliberately `config.celery_app.tasks[name].apply_async(...)` -- looking
the task up in the app's OWN registry and calling `apply_async` on the
real `Task` object -- rather than `celery.current_app.send_task(name,
...)`. Two real, verified reasons, not a style preference:

1. `Celery.send_task()` explicitly does NOT honor
   `CELERY_TASK_ALWAYS_EAGER` (Celery's own source emits an
   `AlwaysEagerIgnored` warning for this) -- it always publishes to the
   real broker, which would silently no-op in this test suite (no worker
   consumes the queue during tests) and make this whole path untestable
   without a running worker. `Task.apply_async()` DOES honor eager mode.
2. `celery.current_app` is a thread-local proxy; resolving it from
   inside a `transaction.on_commit()` callback (which can run on a
   different thread than the one that imported `config.celery`,
   observed directly while building this) can resolve to an
   unconfigured default app with no tasks registered at all, rather than
   this project's real `Celery("saas")` instance. Importing the concrete
   app object sidesteps that ambiguity entirely.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.core.models import EventLog
from config.celery import app as celery_app


def emit_domain_event(
    *,
    event_type: str,
    store_id: uuid.UUID | str | None,
    aggregate_type: str,
    aggregate_id: uuid.UUID | str,
    payload: dict[str, Any] | None = None,
) -> EventLog:
    """
    Must be called inside the caller's own open `transaction.atomic()`
    block. `payload` must contain identifiers/audit context ONLY (e.g.
    `order_number`, never `total_amount`/`email`/anything a consumer
    should instead re-read fresh from the authoritative model) -- this
    is explicitly not a second financial/business snapshot of whatever
    the event is about.
    """
    event = EventLog.objects.create(
        store_id=store_id,
        event_type=event_type,
        payload={
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            **(payload or {}),
        },
    )

    task_names: list[str] = settings.DOMAIN_EVENT_CONSUMER_TASKS.get(event_type, [])
    for task_name in task_names:

        def _enqueue(name: str = task_name, event_id: uuid.UUID = event.id) -> None:
            celery_app.tasks[name].apply_async(kwargs={"event_id": str(event_id)})

        transaction.on_commit(_enqueue)
    return event
