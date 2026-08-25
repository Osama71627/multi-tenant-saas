"""
RFC 9457 ("Problem Details for HTTP APIs")-shaped error responses for the
whole platform, so every API surface (auth/platform/dashboard/storefront)
returns errors Next.js can parse identically. See docs/ARCHITECTURE.md
section 5.2.
"""

from __future__ import annotations

import uuid

from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler


class TenantMismatchError(Exception):
    """
    Raised when code asks for a tenant-owned object that doesn't belong to
    the tenant currently active on the request. Always surfaced to the
    client as 404, never 403 -- a 403 confirms the object exists in
    another store, which is itself a data leak. See docs/ARCHITECTURE.md
    section 12 (threat scenario #1/#2).
    """


def _error_type_for(exc: Exception) -> str:
    return exc.__class__.__name__


def rfc9457_exception_handler(exc, context):
    if isinstance(exc, TenantMismatchError | Http404):
        exc = drf_exceptions.NotFound()

    response: Response | None = drf_default_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    errors = None
    if isinstance(detail, dict) and "detail" not in detail:
        errors = [{"field": field, "messages": messages} for field, messages in detail.items()]
        detail = "Validation failed."
    elif isinstance(detail, dict):
        detail = detail.get("detail", str(detail))

    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None
    title = getattr(exc, "default_detail", None) or str(exc)

    response.data = {
        "type": _error_type_for(exc),
        "title": title,
        "status": response.status_code,
        "detail": str(detail),
        "request_id": request_id or str(uuid.uuid4()),
    }
    if errors:
        response.data["errors"] = errors
    return response


__all__ = [
    "TenantMismatchError",
    "rfc9457_exception_handler",
    "status",
]
