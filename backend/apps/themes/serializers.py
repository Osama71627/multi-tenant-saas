from __future__ import annotations

from rest_framework import serializers

from apps.themes.models import StoreThemeConfig, ThemePreset


class ThemePresetSerializer(serializers.ModelSerializer):
    theme_code = serializers.CharField(source="theme_version.theme.code", read_only=True)
    theme_version_number = serializers.IntegerField(
        source="theme_version.version_number", read_only=True
    )

    class Meta:
        model = ThemePreset
        fields = [
            "id",
            "name",
            "default_settings",
            "preview_image_url",
            "is_default",
            "theme_code",
            "theme_version_number",
        ]
        read_only_fields = fields


class StoreThemeConfigSerializer(serializers.ModelSerializer):
    theme_code = serializers.CharField(source="theme_version.theme.code", read_only=True)
    theme_version_number = serializers.IntegerField(
        source="theme_version.version_number", read_only=True
    )

    class Meta:
        model = StoreThemeConfig
        fields = [
            "id",
            "theme_code",
            "theme_version_number",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class StorefrontStoreSerializer(serializers.Serializer):
    """Plain `serializers.Serializer`, not bound to `apps.stores.models.Store`
    -- only the public-safe subset a shopper may see, assembled by the
    view from `request.tenant_store`. Never the full dashboard
    `StoreDetailSerializer` shape (that includes `contact_email`/
    `contact_phone`, merchant-only)."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    default_currency = serializers.CharField()


class StorefrontContextSerializer(serializers.Serializer):
    """Phase 13: everything the storefront renderer needs for one
    request -- who the store is (public fields only) and which
    theme/settings to render with. One call, not two, since every
    storefront page needs both."""

    store = StorefrontStoreSerializer()
    theme = StoreThemeConfigSerializer()
