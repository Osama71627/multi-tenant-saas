"""
apps.stores' HTTP surface.

The last diagnostic endpoint (`tenant_context_debug`, storefront/Host-
based resolution) was removed in Phase 6: `apps.carts`' storefront
endpoints are now real endpoints exercising that exact same
`TenantMiddleware` Host-based resolution path, so the diagnostic
duplicate is gone -- the dashboard-path debug route was already removed
the same way back in Phase 3 once `StoreDetailView` shipped
(docs/PHASE_1_REPORT.md, PHASE_2_REPORT.md, PHASE_3_REPORT.md all
flagged this one for removal "once a real endpoint lands"; this is that
moment for the storefront side).
"""

from __future__ import annotations

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PlatformUser
from apps.stores import services
from apps.stores.hooks import PostCreationHookError
from apps.stores.mixins import StoreScopedAPIView
from apps.stores.serializers import (
    CreateStoreSerializer,
    StoreDetailSerializer,
    StoreListItemSerializer,
    UpdateStoreSerializer,
)
from apps.stores.services import StoreSlugReservedError


class StoreListCreateView(APIView):
    """`GET /api/v1/dashboard/stores` -- the store switcher's data source
    (docs/ARCHITECTURE.md section 7.3): stores the current user has an
    ACTIVE membership in; see apps.stores.services.list_stores_for_user
    for why this is a legitimate cross-tenant read. `POST` is the
    existing store-provisioning endpoint, unchanged."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "store_create"

    def get_throttles(self):
        # `throttle_scope`/ScopedRateThrottle applies per-VIEW, not
        # per-method -- without this override, listing stores would be
        # throttled at the store_create rate (10/hour) too, which is
        # wrong: only provisioning a new store is the expensive,
        # abuse-prone operation this scope exists to protect.
        if self.request.method == "GET":
            return []
        return super().get_throttles()

    @extend_schema(responses=StoreListItemSerializer(many=True))
    def get(self, request: Request) -> Response:
        if not isinstance(request.user, PlatformUser):
            raise exceptions.PermissionDenied
        stores = services.list_stores_for_user(user=request.user)
        return Response(StoreListItemSerializer(stores, many=True).data)

    @extend_schema(request=CreateStoreSerializer, responses={201: StoreDetailSerializer})
    def post(self, request: Request) -> Response:
        # IsAuthenticated guarantees this at runtime; mypy otherwise sees
        # `request.user` as `PlatformUser | AnonymousUser`.
        if not isinstance(request.user, PlatformUser):
            raise exceptions.PermissionDenied

        serializer = CreateStoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            store = services.create_store(owner=request.user, **serializer.validated_data)
        except StoreSlugReservedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PostCreationHookError as exc:
            # A registered hook (e.g. apps.themes: an invalid/inactive
            # theme_preset_id) rejected this creation -- the whole
            # transaction already rolled back (apps/stores/services.py),
            # so there is no partially-provisioned Store to clean up here.
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            # The authoritative guard against a same-slug race that the
            # serializer's pre-check can't fully close -- see
            # apps/stores/services.py:create_store.
            return Response(
                {"detail": "A store with this slug already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StoreDetailSerializer(store).data, status=status.HTTP_201_CREATED)


class StoreDetailView(StoreScopedAPIView):
    """404 vs 403 semantics, and why: apps/stores/mixins.py:StoreScopedAPIView."""

    @extend_schema(responses=StoreDetailSerializer)
    def get(self, request: Request, store_id) -> Response:
        return Response(StoreDetailSerializer(self.store).data)

    @extend_schema(request=UpdateStoreSerializer, responses={200: StoreDetailSerializer})
    def patch(self, request: Request, store_id) -> Response:
        serializer = UpdateStoreSerializer(self.store, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "A store with this slug already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StoreDetailSerializer(self.store).data)
