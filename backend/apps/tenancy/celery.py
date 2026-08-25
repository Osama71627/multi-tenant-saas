"""
Celery task base classes that make tenant context explicit instead of
ambient.

Worker processes are long-lived and handle jobs for many different stores
over their lifetime. If a task could inherit "whatever tenant was active
last," a bug becomes "background job silently ran against the wrong
store's data" -- one of the scenarios docs/DECISIONS.md explicitly calls
out. So: `TenantTask` subclasses must be dispatched through
`dispatch_for_store(task, store_id, ...)`, which fails at *dispatch* time
(not deep inside the task) if store_id is missing.
"""

from __future__ import annotations

import uuid

from celery import Task
from django.db import transaction

from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

_TENANT_KWARG = "_tenant_store_id"


class TenantTask(Task):
    """
    Base class for every Celery task that reads or writes tenant-owned
    data. Wraps the task body in the same context-setting + transaction
    pattern `TenantMiddleware` uses for HTTP requests, so `Model.objects`
    inside the task is correctly scoped and RLS-protected.
    """

    abstract = True
    # Celery's default arg-typing check inspects the wrapped function's
    # own signature, which never declares `_tenant_store_id` (it's popped
    # inside `__call__` below, before the real task body ever sees it) --
    # so the built-in check would reject every dispatch before it even
    # reaches our own, clearer validation. Turn it off for this base.
    typing = False

    def __call__(self, *args, **kwargs):
        store_id = kwargs.pop(_TENANT_KWARG, None)
        if store_id is None:
            raise TypeError(
                f"{self.name} is a TenantTask and must be dispatched via "
                "apps.tenancy.celery.dispatch_for_store(task, store_id, ...), "
                "never task.delay(...)/apply_async(...) directly."
            )
        store_uuid = uuid.UUID(str(store_id))
        with tenant_context(TenantContext(store_id=store_uuid)):
            with transaction.atomic(using="default"):
                apply_tenant_context_to_db(store_uuid, using="default")
                try:
                    return super().__call__(*args, **kwargs)
                finally:
                    clear_tenant_context_from_db(using="default")


class PlatformTask(Task):
    """
    Explicitly tenant-less task (platform-wide analytics rollups,
    scheduling fan-out, etc.). No ambient tenant is set -- use
    `Model.unscoped` deliberately for any cross-tenant read/write inside
    one of these, so it's obvious in review that it's intentional.
    """

    abstract = True


def dispatch_for_store(task: Task, store_id: uuid.UUID | str, *args, **kwargs):
    """The only sanctioned way to enqueue a `TenantTask`."""
    kwargs[_TENANT_KWARG] = str(store_id)
    return task.apply_async(args=args, kwargs=kwargs)
