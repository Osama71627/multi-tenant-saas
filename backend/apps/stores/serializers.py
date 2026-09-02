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
    # Real gap found live: Store.logo (Phase F's business-info upload)
    # was write-only -- saved to disk correctly, but never returned by
    # ANY serializer, so nothing anywhere could show the merchant their
    # own uploaded logo back. SerializerMethodField (not a plain
    # ImageField) because this is read-only here on purpose -- editing
    # the logo is a separate, not-yet-built settings flow; `.url`
    # raises ValueError on an empty ImageField, so `None` for "no logo
    # set" has to be handled explicitly. Absolute, not the bare
    # MEDIA_URL-relative path, so the browser (a different origin
    # entirely from Django -- see docs/ARCHITECTURE.md) can load it
    # directly with a plain `<img src>`, no BFF proxying needed (public,
    # unauthenticated storefront images already work the identical way).
    logo = serializers.SerializerMethodField()
    # Real gap found live: the dashboard's "Preview store" button opened
    # its own internal fixture-data preview (small bundled demo
    # products, see apps/themes/models.py's own "no DemoStore" docstring)
    # unconditionally -- including for a merchant who already has a real
    # Store with real products, which is actively misleading (looks like
    # your storefront, isn't). That internal preview still has a real,
    # separate job (theme browsing before a real Store exists, e.g. the
    # public marketplace preview) and is untouched; this field exists so
    # the dashboard can instead link to the merchant's OWN real live
    # storefront. `StoreDomain.hostname` (not slug + a frontend-derived
    # root domain) so this stays correct automatically if/when a
    # merchant ever attaches a real custom domain (`StoreDomain.kind`
    # already models that, unused today) -- the frontend never
    # reconstructs a hostname itself. `None` only for a Store somehow
    # missing its always-created-at-signup primary domain row.
    primary_domain = serializers.SerializerMethodField()

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
            "logo",
            "primary_domain",
            "created_at",
        ]
        read_only_fields = fields

    def get_logo(self, obj: Store) -> str | None:
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

    def get_primary_domain(self, obj: Store) -> str | None:
        # `.unscoped`, not `.objects` -- deliberately, matching
        # apps.stores.middleware's own identical choice for this exact
        # model: `StoreDomain.objects` (TenantManager) raises
        # TenantContextMissingError whenever no store-scoped GUC is set
        # on the request (e.g. the store LIST endpoint, which spans
        # every store a user owns -- no single tenant context to set).
        # This does not bypass RLS -- StoreDomain's own SELECT policy is
        # already open (`USING (true)`, see its model docstring: hostnames
        # are public information), `.unscoped` just skips the
        # application-level "which tenant?" check that `.objects` adds
        # on top of RLS for models that actually need one.
        domain = StoreDomain.unscoped.filter(store=obj, is_primary=True).first()
        return domain.hostname if domain else None


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
    # See StoreDetailSerializer.logo's own comment -- same gap, same fix,
    # needed here too since the store switcher (every page's own header)
    # reads from THIS serializer, not StoreDetailSerializer.
    logo = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ["id", "name", "slug", "status", "logo"]
        read_only_fields = fields

    def get_logo(self, obj: Store) -> str | None:
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
