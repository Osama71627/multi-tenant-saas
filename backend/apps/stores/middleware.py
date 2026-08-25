"""
Layer 1 of the isolation defense: resolves which Store (if any) a request
belongs to, and publishes it via apps.tenancy.context + the PostgreSQL
session GUC (apps.tenancy.db).

Lives in `apps.stores`, not `apps.tenancy`, on purpose: resolving "which
store is this" inherently requires knowing about `Store`/`StoreDomain`,
and `apps.tenancy` must stay a domain-agnostic mechanism that domain apps
depend ON, never the reverse -- see the dependency rule in
docs/ARCHITECTURE.md section 3 and the `import-linter` contract in
pyproject.toml, which enforces this direction automatically.

Deliberately does NOT check authorization (is this user allowed to see
this store?) -- that is handled by DRF permission classes further down
the stack, after AuthenticationMiddleware has run. Tenant *resolution*
must never depend on *who* is asking. See docs/ARCHITECTURE.md section 11.

Resolution strategy per API surface (docs/ARCHITECTURE.md section 5.1):
  - /api/v1/storefront/*                        -> Host header -> StoreDomain
  - /api/v1/dashboard/stores/<uuid:id>/*         -> the <id> path segment
  - /api/v1/webhooks/payments/<provider>/<uuid>  -> the <uuid> path segment
    (Phase 9 -- a webhook has no Host to trust and no authenticated user;
    the store_id in the URL is only ever used to resolve the tenant
    context/RLS scope for the LOOKUP that follows, never treated as a
    security boundary by itself -- apps.payments.services.process_webhook
    still verifies the provider's signature before any side effect)
  - /api/v1/platform/*, /admin/, /healthz        -> no tenant (by design)

Every request -- tenant or not -- is wrapped in one `transaction.atomic()`
block owned by this middleware (not Django's ATOMIC_REQUESTS, which only
wraps the view; see the note in config/settings/base.py), and the GUC is
always explicitly set, including to "no tenant" (empty string) when none
resolves. That unconditional set is what prevents a pooled/reused
connection from leaking one request's tenant into the next.
"""

from __future__ import annotations

import re
import uuid

from django.core.cache import cache
from django.db import transaction

from apps.stores.models import Store, StoreDomain
from apps.tenancy.context import TenantContext, reset_current_tenant, set_current_tenant
from apps.tenancy.db import apply_tenant_context_to_db

_DASHBOARD_STORE_ID_RE = re.compile(
    r"^/api/v1/dashboard/stores/(?P<store_id>[0-9a-fA-F-]{36})(?:/|$)"
)
_WEBHOOK_STORE_ID_RE = re.compile(
    r"^/api/v1/webhooks/payments/[^/]+/(?P<store_id>[0-9a-fA-F-]{36})/?$"
)
_STOREFRONT_PREFIXES = ("/api/v1/storefront/", "/api/v1/_tenant/")
_DOMAIN_CACHE_TTL_SECONDS = 60
_DOMAIN_CACHE_NEGATIVE_TTL_SECONDS = 15


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with transaction.atomic(using="default"):
            store = self._resolve_store(request)
            request.tenant_store = store

            apply_tenant_context_to_db(store.id if store else None, using="default")
            token = set_current_tenant(
                TenantContext(store_id=store.id, store_slug=store.slug) if store else None
            )
            try:
                response = self.get_response(request)
            finally:
                reset_current_tenant(token)
        return response

    def _resolve_store(self, request):
        path = request.path

        if path.startswith(_STOREFRONT_PREFIXES):
            return self._resolve_by_host(request)

        match = _DASHBOARD_STORE_ID_RE.match(path)
        if match:
            return self._resolve_by_id(match.group("store_id"))

        match = _WEBHOOK_STORE_ID_RE.match(path)
        if match:
            return self._resolve_by_id(match.group("store_id"))

        return None

    @staticmethod
    def _resolve_by_host(request):
        hostname = request.get_host().split(":")[0].lower()
        cache_key = f"tenancy:domain:{hostname}"
        store_id = cache.get(cache_key)

        if store_id is None:
            # `.unscoped`: resolving *which* tenant a hostname belongs to
            # is inherently a pre-tenant lookup. Safe because StoreDomain's
            # RLS SELECT policy is `USING (true)` -- hostnames are public
            # information (that's what DNS is); only writes are
            # tenant-restricted. See apps/stores/migrations.
            try:
                domain = StoreDomain.unscoped.select_related("store").get(hostname=hostname)
            except StoreDomain.DoesNotExist:
                cache.set(cache_key, "", timeout=_DOMAIN_CACHE_NEGATIVE_TTL_SECONDS)
                return None
            store_id = str(domain.store_id)
            cache.set(cache_key, store_id, timeout=_DOMAIN_CACHE_TTL_SECONDS)

        if not store_id:
            return None
        return TenantMiddleware._active_store_or_none(store_id)

    @staticmethod
    def _resolve_by_id(raw_store_id: str):
        try:
            uuid.UUID(raw_store_id)
        except ValueError:
            return None
        return TenantMiddleware._active_store_or_none(raw_store_id)

    @staticmethod
    def _active_store_or_none(store_id: str):
        try:
            return Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return None
