"""
Shared "dashboard endpoint scoped to one store" gate. Introduced in
Phase 4 once a second consumer (apps.catalog, on top of apps.stores'
own StoreDetailView) needed the identical check -- extracting it now is
real reuse, not speculative abstraction.
"""

from __future__ import annotations

from django.http import Http404
from rest_framework import exceptions
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import PlatformUser
from apps.stores import hooks, services
from apps.stores.models import Store


class _PaymentRequired(exceptions.APIException):
    status_code = 402
    default_code = "payment_required"


class StoreScopedAPIView(APIView):
    """
    Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
    endpoint. Relies on `TenantMiddleware` having already resolved the
    path's `store_id` into `request.tenant_store` (path-based, Host
    header ignored -- apps/stores/middleware.py).

    404 vs 403 distinguished on purpose (same reasoning as Phase 3's
    StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
    secret (its RLS SELECT policy is intentionally open), but catalog
    resources INSIDE it are fully RLS-restricted with no such exception
    -- so once past this gate, an ordinary tenant-scoped query for a
    resource that doesn't exist in this store naturally 404s via
    `DoesNotExist`, with no separate leak to worry about.

    Sets `self.store` for subclasses to use.
    """

    permission_classes = [IsAuthenticated]
    store: Store

    def initial(self, request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)

        store = getattr(request, "tenant_store", None)
        if store is None:
            raise Http404

        if not isinstance(request.user, PlatformUser):
            raise exceptions.PermissionDenied

        if not services.is_active_member(user=request.user, store=store):
            raise exceptions.PermissionDenied

        self.store = store

        # Phase 10, approved architecture decision 8/11: a `read_only`
        # Store (subscription lifecycle -- apps.subscriptions.tasks,
        # registered via `apps.stores.hooks.register_write_gate` since
        # apps.stores must never import apps.subscriptions directly)
        # still serves ordinary dashboard READS, only blocks writes.
        if request.method not in SAFE_METHODS:
            try:
                hooks.check_write_gates(store=store)
            except hooks.WriteBlockedError as exc:
                raise _PaymentRequired(str(exc)) from exc


class StorefrontAPIView(APIView):
    """
    Base class for any `/api/v1/storefront/...` endpoint. Relies on
    `TenantMiddleware` having resolved the request's Host header into
    `request.tenant_store` (apps/stores/middleware.py) -- deliberately
    the OPPOSITE resolution path from `StoreScopedAPIView` (Host, never
    a path segment), matching how a real storefront request arrives
    (`store1.example.com`, not `/dashboard/stores/<id>/...`).

    Public/guest-accessible by design (`AllowAny`) -- storefront
    endpoints serve shoppers, not authenticated merchant staff. No
    unresolved-host case is silently allowed through: an unknown
    hostname 404s here, same as a genuinely nonexistent dashboard store.

    Sets `self.store` for subclasses to use.
    """

    permission_classes = [AllowAny]
    store: Store

    def initial(self, request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)

        store = getattr(request, "tenant_store", None)
        if store is None:
            raise Http404

        self.store = store


class WebhookAPIView(APIView):
    """
    Base class for `/api/v1/webhooks/payments/<provider>/<uuid:store_id>`
    (Phase 9) -- the third tenant-resolution strategy, added to
    `TenantMiddleware` alongside dashboard/storefront (see that module's
    docstring). No Host to trust, no authenticated user to check
    membership for (`AllowAny`, same reasoning as `StorefrontAPIView`) --
    the store_id path segment ONLY resolves which tenant's RLS scope to
    look the provider config up in. It is never treated as a security
    boundary by itself: `apps.payments.services.process_webhook` still
    verifies the provider's signature before any side effect, exactly as
    it would for a forged store_id pointing at a real store.

    Sets `self.store` for subclasses to use.
    """

    permission_classes = [AllowAny]
    store: Store

    def initial(self, request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)

        store = getattr(request, "tenant_store", None)
        if store is None:
            raise Http404

        self.store = store
