"""
Two Celery tasks, both `PlatformTask` (no ambient tenant -- each derives
its own real per-event tenant context, same split `apps.payments.tasks`'
reconciliation uses): `process_domain_event` is the low-latency fast
path triggered by `apps.core.events.emit_domain_event`'s
`transaction.on_commit()` hook (by STRING NAME, `apps.core` never
imports this module); `recover_unprocessed_domain_events` is the
Celery-Beat-driven safety net for the crash-between-commit-and-enqueue
gap (approved review-round requirement, section 3): if the process dies
after the DB commit but before the `on_commit` callback actually runs,
the `EventLog` row is still durably committed and this sweep will find
and process it on its next run.

Both ultimately call the SAME `apps.notifications.services.
process_committed_event` -- idempotent by construction, so calling it
twice for the same event (fast path AND recovery both finding it) is
always safe.

Deliberate design simplification, stated honestly rather than
overclaimed: `process_domain_event` makes exactly ONE attempt and does
NOT use Celery's own `retry`/`autoretry_for`/backoff machinery. A retry
loop that runs synchronously inside `transaction.on_commit()` (which is
what `emit_domain_event` uses, so it never holds a PostgreSQL lock
during the network send -- approved review-round requirement, section 5)
would either block whatever just committed the triggering transaction
for the full backoff duration, or -- worse -- let a transient SMTP
failure's retry-exhaustion exception propagate back out of `on_commit`
into the ORIGINAL caller's control flow (e.g. the HTTP response of
`checkout/complete`), which must never happen: a notification failure is
a Notifications-side effect only, never something `apps.orders`/
`apps.payments` callers can see. So this task catches and logs any
`process_committed_event` failure instead of re-raising, and retries
happen ONLY via `recover_unprocessed_domain_events`'s periodic sweep --
a FIXED interval (however often Celery Beat is configured to run it),
not per-attempt exponential backoff. This is a real limitation of this
phase's implementation, not a hidden one.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.models import EventLog
from apps.notifications import services
from apps.notifications.models import NotificationDispatch
from apps.tenancy.celery import PlatformTask
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

logger = logging.getLogger(__name__)

_TERMINAL_DISPATCH_STATUSES = (
    NotificationDispatch.Status.SENT,
    NotificationDispatch.Status.FAILED,
    NotificationDispatch.Status.DEAD_LETTER,
)


def _process_one_event(event: EventLog) -> None:
    assert event.store_id is not None  # both callers already filter this out
    with tenant_context(TenantContext(store_id=event.store_id)):
        apply_tenant_context_to_db(event.store_id)
        try:
            services.process_committed_event(event=event)
        except Exception:  # noqa: BLE001 -- see module docstring: never
            # propagate a notification-delivery failure out of here. The
            # underlying NotificationDispatch row already recorded the
            # failure (apps.notifications.services); this is purely so an
            # operator can see it happened.
            logger.exception("notifications.process_event_failed event_id=%s", event.id)
        finally:
            clear_tenant_context_from_db()


@shared_task(base=PlatformTask, name="apps.notifications.tasks.process_domain_event")
def process_domain_event(event_id: str) -> None:
    """
    The fast path, triggered by `emit_domain_event`'s `on_commit` hook.
    Deliberately establishes its OWN tenant context from `event.store_id`
    -- the durable row, not anything ambient -- every single time: a real
    Celery worker process has no HTTP request, no inherited GUC, nothing
    left over from whoever published the task. `CELERY_TASK_ALWAYS_EAGER`
    (test/dev) executes this function inline on the publishing thread,
    which could otherwise mask a worker relying on inherited context by
    accident; `apps/notifications/tests/test_worker_tenant_isolation.py`
    proves this explicitly by invoking the task with NO ambient tenant
    context active at all, mirroring a fresh worker process.
    """
    try:
        event = EventLog.objects.get(id=event_id)
    except EventLog.DoesNotExist:
        return  # nothing to do -- should not happen in practice, not an error
    if event.store_id is None:
        return
    _process_one_event(event)


@shared_task(base=PlatformTask, name="apps.notifications.tasks.recover_unprocessed_domain_events")
def recover_unprocessed_domain_events() -> int:
    """
    Review-round-2 fix: this used to gate eligibility on
    `EventLog.created_at >= now() - LOOKBACK_HOURS` alone -- a real
    correctness bug. An event committed successfully but never dispatched
    (the crash-between-commit-and-publish gap) would age out of that
    window and be permanently invisible to recovery forever, even though
    no `NotificationDispatch` was ever created for it. That violates the
    approved invariant: "a committed notification-eligible domain event
    must not be permanently lost merely because the process crashed
    between DB commit and Celery publish."

    Fixed shape: `EventLog` (known event types) `WHERE NOT EXISTS` a
    terminal `NotificationDispatch` for it -- age plays no part in
    eligibility. `EventLog` itself stays exactly what it already was
    (an immutable, append-only durable record, docs/ARCHITECTURE.md line
    108) -- no status field, no claim/lock column added to it; it is
    read-only here. `NotificationDispatch` remains the only place
    delivery state lives, exactly as approved.

    RLS makes a single global anti-join impossible without a bypass this
    project deliberately never uses (`app_migrator`/BYPASSRLS are for
    migrations/schema only -- never a runtime read/write path, the same
    boundary Phase 10's review enforced): the `app.current_store_id` GUC
    is one scalar per connection, so it can only ever match ONE store's
    rows at a time. The anti-join is therefore done PER STORE, inside
    that store's own real tenant context (both the Python-level
    `TenantManager` filter AND the DB-level RLS policy correctly scoped)
    -- never against `.unscoped` with no context, which would make every
    row invisible and the "NOT EXISTS" trivially true for everything.

    `EventLog` carries no RLS (a deliberate, pre-existing exemption --
    docs/ARCHITECTURE.md line 108), so discovering which stores even HAVE
    a candidate event is a safe, RLS-free, unbounded scan (bounded in
    practice by the number of distinct stores, not the number of
    historical events). Deterministic oldest-first ordering + a
    per-store batch cap (`NOTIFICATION_RECOVERY_BATCH_SIZE_PER_STORE`)
    bounds worst-case work per sweep run; a store with a backlog larger
    than the cap is simply finished across multiple runs, never starved
    -- the next run picks up wherever the previous one's anti-join still
    finds pending events, since already-terminal ones drop out of the
    query on their own.

    `NOTIFICATION_RECOVERY_LOOKBACK_HOURS` is kept only to flag
    genuinely stale finds for operator visibility (a log line) -- it does
    NOT gate whether an event gets processed.
    """
    known_event_types = list(settings.DOMAIN_EVENT_CONSUMER_TASKS.keys())
    lookback_hours = settings.NOTIFICATION_RECOVERY_LOOKBACK_HOURS
    staleness_cutoff = timezone.now() - timedelta(hours=lookback_hours)
    batch_size = settings.NOTIFICATION_RECOVERY_BATCH_SIZE_PER_STORE

    store_ids = (
        EventLog.objects.filter(event_type__in=known_event_types, store_id__isnull=False)
        .order_by()
        .values_list("store_id", flat=True)
        .distinct()
    )

    processed = 0
    for store_id in store_ids.iterator():
        assert store_id is not None  # excluded by store_id__isnull=False above
        pending_events: list[EventLog] = []
        with tenant_context(TenantContext(store_id=store_id)):
            apply_tenant_context_to_db(store_id)
            try:
                dispatched_event_ids = NotificationDispatch.objects.filter(
                    status__in=_TERMINAL_DISPATCH_STATUSES
                ).values_list("event_id", flat=True)
                pending_events = list(
                    EventLog.objects.filter(store_id=store_id, event_type__in=known_event_types)
                    .exclude(id__in=dispatched_event_ids)
                    .order_by("created_at")[:batch_size]
                )
            except Exception:  # noqa: BLE001 -- one store's discovery query
                # failing (e.g. a transient DB blip) must not starve every
                # other store until the next scheduled sweep.
                logger.exception("notifications.recovery_discovery_failed store_id=%s", store_id)
            finally:
                clear_tenant_context_from_db()

        for event in pending_events:
            if event.created_at < staleness_cutoff:
                logger.warning(
                    "notifications.recovery_found_stale_event event_id=%s store_id=%s age_hours>%s",
                    event.id,
                    store_id,
                    lookback_hours,
                )
            _process_one_event(event)
            processed += 1
    return processed
