"""
Deliberately separate from apps.core.exceptions (which imports DRF's
`rest_framework.views` at module level for the RFC 9457 handler).
apps.tenancy.models is imported very early -- during Django's app
registry population, before every app's models are guaranteed loaded --
and pulling in DRF (which, via `rest_framework.schemas`, eagerly resolves
`DEFAULT_AUTHENTICATION_CLASSES` at import time) from there created a real
circular-import failure the moment that setting pointed at a class in an
app loaded later in INSTALLED_APPS. Keeping tenancy's own exception types
here, with zero DRF/app dependencies, avoids that whole class of ordering
bug rather than papering over one instance of it.
"""

from __future__ import annotations


class TenantContextMissingError(Exception):
    """Raised when tenant-scoped ORM access is attempted with no tenant
    resolved on the current request/task. Fail closed, never silently
    return cross-tenant or unfiltered data."""
