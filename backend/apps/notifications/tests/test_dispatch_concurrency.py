"""
Conditional required test (Phase 11 review round, Section 20): two
workers can genuinely consume the SAME domain event concurrently (the
fast-path task racing the recovery sweep, or two recovery-sweep runs
overlapping) -- `apps.notifications.services.process_committed_event`
relies on `NotificationDispatch`'s own DB uniqueness (`(store, event,
channel, notification_type)`, apps/notifications/migrations/
0001_initial.py) via `get_or_create` to prevent a duplicate row, exactly
the invariant apps/payments/tests/test_concurrency.py already proves for
`WebhookEvent`/`PaymentIntent` -- same pattern reused here: two genuinely
separate `app_user` PostgreSQL sessions, real threads, a barrier so both
attempts overlap, `app_migrator` for setup/teardown with real commits.

Honest scope limit, stated explicitly per the review's requirement: this
proves exactly one LOCAL dispatch-decision row is ever created -- it says
nothing about whether two concurrent successful sends could still reach
the SMTP provider twice (that ambiguity is about the network call itself,
not this table's concurrency safety, and is documented separately in
docs/PHASE_11_REPORT.md).
"""

from __future__ import annotations

import threading

import psycopg
import pytest
from django.db import connections

from apps.core.uuid7 import uuid7

pytestmark = pytest.mark.django_db


def _insert_store(conn, store_id: str, slug: str) -> None:
    conn.execute(
        "INSERT INTO stores_store "
        "(id, created_at, updated_at, name, slug, status, default_currency, "
        "contact_email, contact_phone) "
        "VALUES (%s, now(), now(), 'Dispatch Race Co', %s, 'active', 'SAR', '', '')",
        [store_id, slug],
    )


def _insert_event(conn, event_id: str, store_id: str, order_id: str) -> None:
    conn.execute(
        "INSERT INTO core_eventlog (id, created_at, updated_at, store_id, event_type, payload) "
        "VALUES (%s, now(), now(), %s, 'order.confirmed', %s::jsonb)",
        [
            event_id,
            store_id,
            f'{{"aggregate_type": "order", "aggregate_id": "{order_id}"}}',
        ],
    )


def _claim_dispatch(user_params, *, store_id, event_id, order_id) -> str:
    """Mirrors the claim half of `process_committed_event`'s `get_or_create`
    -- an INSERT that relies on the unique constraint to reject a racing
    duplicate, exactly what Django's `get_or_create` does under the hood
    when its initial `get()` misses and two callers both fall through to
    `create()`."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            try:
                cur.execute(
                    "INSERT INTO notifications_notificationdispatch "
                    "(id, created_at, updated_at, notification_type, channel, recipient, "
                    "status, attempts, last_error, sent_at, event_id, store_id) "
                    "VALUES (%s, now(), now(), 'order_confirmation', 'email', "
                    "'race@example.com', 'pending', 0, '', NULL, %s, %s)",
                    [str(uuid7()), event_id, store_id],
                )
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                return "duplicate"
        conn.commit()
        return "claimed"
    finally:
        conn.close()


def test_concurrent_claims_for_the_same_event_yield_exactly_one_dispatch_row():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id, order_id, event_id = (str(uuid7()) for _ in range(3))

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"dispatch-race-{store_id[:8]}")
        _insert_event(setup_conn, event_id, store_id, order_id)

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(
                _claim_dispatch(
                    user_params, store_id=store_id, event_id=event_id, order_id=order_id
                )
            )

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["claimed", "duplicate"], results

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM notifications_notificationdispatch WHERE event_id = %s",
                [event_id],
            )
            (dispatch_count,) = cur.fetchone()
        assert dispatch_count == 1  # exactly one logical dispatch, not two
    finally:
        setup_conn.execute(
            "DELETE FROM notifications_notificationdispatch WHERE store_id = %s", [store_id]
        )
        setup_conn.execute("DELETE FROM core_eventlog WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()
