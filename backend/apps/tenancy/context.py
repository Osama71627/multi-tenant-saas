"""
Per-request/per-task tenant context.

Uses `contextvars.ContextVar`, NOT `threading.local`. This matters:
Django can run under ASGI (we ship `config/asgi.py` for future use), and
`threading.local` does not follow a single logical request/task through
async task-switching the way `ContextVar` does -- using thread-local here
would risk one coroutine reading another's tenant. See
docs/ARCHITECTURE.md section 2.3, layer 1.
"""

from __future__ import annotations

import contextlib
import contextvars
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    store_id: uuid.UUID
    store_slug: str = ""


_current_tenant: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "current_tenant", default=None
)


def get_current_tenant() -> TenantContext | None:
    return _current_tenant.get()


def get_current_store_id() -> uuid.UUID | None:
    tenant = _current_tenant.get()
    return tenant.store_id if tenant is not None else None


def set_current_tenant(tenant: TenantContext | None) -> contextvars.Token:
    return _current_tenant.set(tenant)


def reset_current_tenant(token: contextvars.Token) -> None:
    _current_tenant.reset(token)


@contextlib.contextmanager
def tenant_context(tenant: TenantContext | None):
    """Convenience context manager: `with tenant_context(ctx): ...`."""
    token = set_current_tenant(tenant)
    try:
        yield tenant
    finally:
        reset_current_tenant(token)
