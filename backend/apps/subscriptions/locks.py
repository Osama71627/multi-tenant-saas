"""
Single source of truth for the advisory-lock namespace used to serialize
"live-COUNT-derived" quota checks (currently: `products` -- see
apps.subscriptions.entitlements). Approved architecture decision 6:
"وثّق lock namespace في utility واحدة ولا تنسخ key-generation logic في
عدة apps" -- every caller goes through `acquire_quota_lock`, never
constructs the two `hashtext()` keys itself.

Why `pg_advisory_xact_lock(key1, key2)` (the two-int32 overload) rather
than the single-bigint form on a combined string: two independent
`hashtext()` values (one over the store id, one over the quota key)
means a collision requires BOTH 32-bit hashes to collide simultaneously
for an unrelated (store, quota_key) pair, rather than one 32-bit hash of
a concatenated string. The lock is transaction-scoped
(`pg_advisory_xact_lock`, not `pg_advisory_lock`) so it releases
automatically at COMMIT or ROLLBACK -- never needs (and must never get)
an explicit unlock call, matching every other lock primitive already
used in this project (`SELECT ... FOR UPDATE`).

This only serializes CONCURRENT usage-increasing mutations against the
SAME (store, quota_key) pair for the duration of one transaction; it is
not a general-purpose distributed lock and must not be reused for
anything outside quota enforcement.
"""

from __future__ import annotations

import uuid

from django.db import connection


def acquire_quota_lock(store_id: uuid.UUID | str, quota_key: str) -> None:
    """Must be called inside an open `transaction.atomic()` block."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
            [str(store_id), quota_key],
        )
