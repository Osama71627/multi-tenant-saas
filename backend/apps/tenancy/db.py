"""
Bridges the Python-level tenant context (apps.tenancy.context) to the
PostgreSQL session that Row-Level Security policies actually check.

Security-critical detail: we use `SELECT set_config(name, value, is_local)`
via a parameterized query, NEVER `SET LOCAL app.current_store_id = '...'`
built with string formatting. `SET`/`SET LOCAL` do not support bind
parameters in SQL, so building one with an f-string is a SQL injection
foot-gun even though `store_id` is normally a trusted UUID we generated
ourselves -- `set_config()` is a normal function call and takes a real
bound parameter. See docs/ARCHITECTURE.md section 2.3, layer 4.

`is_local=true` scopes the setting to the current transaction only (the
functional equivalent of `SET LOCAL`), which is what makes this safe to
use with pgbouncer in transaction-pooling mode and with Django's
persistent connections (CONN_MAX_AGE > 0): the GUC evaporates the moment
the transaction ends, so the next request/task on a reused connection
starts from a clean slate rather than inheriting whatever tenant the
previous request set. `TenantMiddleware` and `TenantTask` are responsible
for making sure this call always happens inside a transaction that spans
the whole request/task -- see the ATOMIC_REQUESTS note in
config/settings/base.py.
"""

from __future__ import annotations

import uuid

from django.db import connections

_GUC_NAME = "app.current_store_id"


def apply_tenant_context_to_db(store_id: uuid.UUID | str | None, using: str = "default") -> None:
    connection = connections[using]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config(%s, %s, true)",
            [_GUC_NAME, str(store_id) if store_id else ""],
        )


def clear_tenant_context_from_db(using: str = "default") -> None:
    # Real bug found wiring apps.subscriptions.services'
    # _create_store_with_unique_slug (Phase F): callers commonly invoke
    # this from a `finally:` block that wraps the very query that might
    # have just failed (e.g. `Store.objects.create(...)` raising
    # `IntegrityError` on a slug collision). At that point Postgres has
    # already aborted the transaction -- ANY further query, including
    # this cleanup one, raises "current transaction is aborted" (surfaced
    # by Django as `TransactionManagementError`), which then MASKS the
    # original, actually-meaningful exception before it ever reaches the
    # caller. The cleanup is redundant on that path anyway:
    # `apply_tenant_context_to_db` above always sets this GUC with
    # `is_local=true` (transaction-scoped), so it evaporates on its own
    # the instant the enclosing `transaction.atomic()` rolls back to its
    # savepoint -- there is nothing left to clear. Skip the no-op query
    # when the connection already knows it needs a rollback.
    connection = connections[using]
    if connection.needs_rollback:
        return
    apply_tenant_context_to_db(None, using=using)
