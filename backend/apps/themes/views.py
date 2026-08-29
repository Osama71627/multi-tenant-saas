"""
apps.themes' HTTP surface. Two read-only endpoints for Phase 12:

- `ThemePresetListView` -- flat, NOT store-scoped (same shape as
  `apps.stores.views.CreateStoreView`): the onboarding wizard's Choose
  step needs to list presets BEFORE a store exists at all, so this
  can't live under `/dashboard/stores/{store_id}/...`.
- `StoreThemeConfigView` -- store-scoped, for the dashboard's "Manage"
  surface to show the store's current theme assignment.

Writes (changing a store's theme/settings after creation) are
deliberately not built in this Phase-12 chunk -- provisioning at
`create_store` time is the approved, required path (see
apps/stores/services.py); a later chunk of this same phase can add a
dashboard-side "change theme" write endpoint reusing
`apps.themes.schemas.validate_settings` for the same allowlist
enforcement, without needing any new architectural decision.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.mixins import StorefrontAPIView, StoreScopedAPIView
from apps.themes.models import StoreThemeConfig, ThemePreset
from apps.themes.serializers import (
    PublicThemePresetSerializer,
    StorefrontContextSerializer,
    StoreThemeConfigSerializer,
    ThemePresetSerializer,
)


class ThemePresetListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=ThemePresetSerializer(many=True))
    def get(self, request: Request) -> Response:
        presets = ThemePreset.objects.filter(is_active=True).select_related("theme_version__theme")
        return Response(ThemePresetSerializer(presets, many=True).data)


class PublicThemePresetListView(APIView):
    """Phase B: the public theme marketplace's data source. Genuinely
    unauthenticated (`AllowAny`) -- the whole point of the marketplace
    is that a visitor browses it BEFORE registering. Read-only,
    platform-global, RLS-readonly data (same `Theme`/`ThemeVersion`/
    `ThemePreset` rows `ThemePresetListView` already serves to
    authenticated onboarding) -- exposing it publicly adds no new
    write surface and leaks nothing merchant-specific."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PublicThemePresetSerializer(many=True))
    def get(self, request: Request) -> Response:
        presets = (
            ThemePreset.objects.filter(is_active=True, theme_version__theme__is_active=True)
            .select_related("theme_version__theme")
            .order_by("theme_version__theme__code")
        )
        return Response(PublicThemePresetSerializer(presets, many=True).data)


class PublicThemePresetDetailView(APIView):
    """One preset's full data for the public preview page -- same
    access rules as the list view above."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PublicThemePresetSerializer)
    def get(self, request: Request, preset_id) -> Response:
        # `preset_id` is anonymous-client-supplied input, unlike
        # StorefrontContextView's `.get(store=self.store)` above (which
        # is structurally guaranteed to exist by provisioning
        # invariants) -- a real 404 case, so `get_object_or_404` (raises
        # `Http404`, converted to a clean 404 by
        # `apps.core.exceptions.rfc9457_exception_handler`) rather than
        # an unguarded `.get()`.
        preset = get_object_or_404(
            ThemePreset.objects.select_related("theme_version__theme"),
            id=preset_id,
            is_active=True,
            theme_version__theme__is_active=True,
        )
        return Response(PublicThemePresetSerializer(preset).data)


class StoreThemeConfigView(StoreScopedAPIView):
    @extend_schema(responses=StoreThemeConfigSerializer)
    def get(self, request: Request, store_id) -> Response:
        config = StoreThemeConfig.objects.select_related("theme_version__theme").get(
            store=self.store
        )
        return Response(StoreThemeConfigSerializer(config).data)


class StorefrontContextView(StorefrontAPIView):
    """Phase 13: `GET /api/v1/storefront/context` -- the one call every
    storefront page needs before it can render anything (which store,
    which theme, which settings). Host-resolved like every other
    storefront endpoint; see `StorefrontAPIView`."""

    @extend_schema(responses=StorefrontContextSerializer)
    def get(self, request: Request) -> Response:
        config = StoreThemeConfig.objects.select_related("theme_version__theme").get(
            store=self.store
        )
        return Response(
            StorefrontContextSerializer(
                {
                    "store": {
                        "id": self.store.id,
                        "name": self.store.name,
                        "default_currency": self.store.default_currency,
                        "logo": self.store.logo,
                    },
                    "theme": config,
                },
                context={"request": request},
            ).data
        )
