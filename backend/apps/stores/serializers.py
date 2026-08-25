from __future__ import annotations

from rest_framework import serializers

from apps.stores.models import Store, StoreDomain
from apps.stores.services import RESERVED_SLUGS


class CreateStoreSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=63)
    # Phase 12, Theme/Template decision (approved Option B): the
    # merchant's chosen ThemePreset from the onboarding wizard's Choose
    # step. Optional -- omitting it provisions the platform's seeded
    # default preset (apps.stores.services.create_store), never leaves a
    # Store with no theme assigned. Existence/active-state is checked in
    # apps.themes.services.resolve_theme_preset, inside the SAME
    # transaction as Store creation -- an invalid id rolls the whole
    # creation back, it never reaches a two-step "store exists, theme
    # pending" state.
    theme_preset_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate_slug(self, value: str) -> str:
        value = value.lower()
        # Authoritative uniqueness is the DB constraint (race-safe); this
        # is just a fast, friendly pre-check for the common case. See
        # apps/stores/views.py for the IntegrityError fallback.
        if Store.objects.filter(slug=value).exists():
            raise serializers.ValidationError("A store with this slug already exists.")
        return value


class StoreDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreDomain
        fields = ["hostname", "kind", "is_primary"]


class StoreDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "default_currency",
            "contact_email",
            "contact_phone",
            "created_at",
        ]
        read_only_fields = fields


class UpdateStoreSerializer(serializers.ModelSerializer):
    """
    PATCH surface for store settings (Phase 12). Deliberately narrow:
    only fields Store itself already authoritatively owns --
    `status` is excluded (subscription-lifecycle-managed, see
    apps.subscriptions.tasks, never merchant-settable directly), and
    nothing here touches StoreDomain/StoreThemeConfig, which have their
    own owners.
    """

    class Meta:
        model = Store
        fields = ["name", "slug", "default_currency", "contact_email", "contact_phone"]

    def validate_slug(self, value: str) -> str:
        value = value.lower()
        if value in RESERVED_SLUGS:
            raise serializers.ValidationError(f"The slug '{value}' is reserved.")
        # Excludes self: this is an update, the store's own current slug
        # must not collide with itself. Authoritative uniqueness is still
        # the DB constraint (race-safe) -- see the view's IntegrityError
        # fallback, same pattern as store creation.
        assert self.instance is not None  # always called with instance=store, never for create
        if Store.objects.exclude(pk=self.instance.pk).filter(slug=value).exists():
            raise serializers.ValidationError("A store with this slug already exists.")
        return value

    def validate_default_currency(self, value: str) -> str:
        return value.upper()


class StoreListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "name", "slug", "status"]
        read_only_fields = fields
