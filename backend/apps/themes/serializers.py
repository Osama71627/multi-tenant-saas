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


class PublicThemePresetSerializer(serializers.ModelSerializer):
    """The public marketplace's card shape -- adds `theme_name`/
    `theme_category` (never needed by the authenticated onboarding
    picker, which already knows which theme it's showing) on top of
    `ThemePresetSerializer`'s fields. A deliberately separate
    serializer, not a superset flag on the same one: the two endpoints
    have different audiences (anonymous visitor vs. an authenticated
    merchant mid-onboarding) and should be free to diverge."""

    theme_code = serializers.CharField(source="theme_version.theme.code", read_only=True)
    theme_name = serializers.CharField(source="theme_version.theme.name", read_only=True)
    theme_category = serializers.CharField(source="theme_version.theme.category", read_only=True)

    class Meta:
        model = ThemePreset
        fields = [
            "id",
            "name",
            "default_settings",
            "preview_image_url",
            "theme_code",
            "theme_name",
            "theme_category",
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
    `contact_phone`, merchant-only). `logo` IS public -- a shopper is
    supposed to see the store's own branding in the header/footer, same
    "public-safe" reasoning that already applies to `name`; real gap
    found live: every storefront theme's header/footer only ever had
    the store NAME to render (plain text wordmark), even for a store
    with a real logo uploaded -- same underlying serializer gap already
    fixed for the dashboard's own StoreListItemSerializer/
    StoreDetailSerializer (apps.stores.serializers)."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    default_currency = serializers.CharField()
    logo = serializers.SerializerMethodField()

    def get_logo(self, obj: dict) -> str | None:
        logo = obj.get("logo")
        if not logo:
            return None
        # Deliberately relative (`/media/...`), NOT `request.
        # build_absolute_uri()` (unlike the dashboard's own StoreListItem/
        # StoreDetail `get_logo`, apps.stores.serializers) -- real bug
        # found live: the storefront's frontend/Django hop crosses TWO
        # different ports in local dev (Next on 4000, Django on 8000),
        # both reached through the SAME tenant hostname. `build_absolute_uri`
        # has only `X-Forwarded-Host` to go on, which is deliberately the
        # bare tenant hostname (needed for RLS/tenant resolution) -- it
        # cannot also know "and reach Django on port 8000, not whichever
        # port issued this request", so it silently built a URL pointing
        # at the STOREFRONT'S OWN port. The frontend already solves this
        # exact problem for its own API calls (lib/backend.ts's
        # `browserBackendOrigin()`, `NEXT_PUBLIC_BACKEND_PORT`) -- a
        # relative path here lets `getStorefrontContext()` apply that
        # same, already-correct origin construction to the logo too,
        # instead of this serializer guessing at a URL it cannot get
        # right from inside one request/response cycle.
        return logo.url


class StorefrontContextSerializer(serializers.Serializer):
    """Phase 13: everything the storefront renderer needs for one
    request -- who the store is (public fields only) and which
    theme/settings to render with. One call, not two, since every
    storefront page needs both."""

    store = StorefrontStoreSerializer()
    theme = StoreThemeConfigSerializer()
