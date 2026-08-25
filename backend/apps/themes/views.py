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

from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.mixins import StorefrontAPIView, StoreScopedAPIView
from apps.themes.models import StoreThemeConfig, ThemePreset
from apps.themes.serializers import (
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
                    },
                    "theme": config,
                }
            ).data
        )
