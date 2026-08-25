"""
Phase 12 review round -- Theme/Template Architecture Decision (Option B,
approved). Full reasoning lives in that decision document; summary of
the load-bearing shape here, mirroring Phase 10's Plan/PlanVersion
pattern deliberately (same reviewer, same already-approved discipline):

1. `Theme`/`ThemeVersion`/`ThemePreset` are platform-global (no
   `store_id`) -- same `global_readonly_policy_sql` RLS shape as
   `subscriptions.Plan`/`notifications.NotificationTemplate`. `app_user`
   has no write policy on these at all; writes happen only via
   `app_migrator` (migrations, fixtures, the `publish_theme_version`/
   `publish_theme_preset` management commands).

2. `ThemeVersion` is immutable once published, exactly like
   `PlanVersion`: a store's `StoreThemeConfig` pins to one specific
   `ThemeVersion` (a normal FK). Updating a theme's rendering contract
   creates a NEW `ThemeVersion` row; existing stores keep rendering on
   their pinned version until an explicit merchant upgrade -- no silent
   auto-migration, ever (approved decision, "Versioning" section).

3. `StoreThemeConfig` is a `TenantOwnedModel` with STANDARD RLS -- no
   exception, same as `Subscription`/`NotificationDispatch`.

4. Deliberately does NOT store store identity/branding (name, logo,
   contact info) -- approved decision's required boundary fix: those
   fields have (or will have, when the onboarding wizard needs them)
   their authoritative home on `apps.stores.models.Store`, never
   duplicated here. `settings` below holds ONLY presentation
   configuration with no existing authoritative owner: palette, font
   choice, hero content, homepage section ordering, nav presentation.

5. `settings` is a JSONField, but never arbitrary: every write is
   validated against an explicit allowlisted serializer keyed by
   `(theme.code, theme_version.version_number)` -- see
   apps/themes/schemas.py. No arbitrary HTML/CSS/JS, no uncontrolled
   JSON keys, same non-negotiable as Phase 11's template-rendering
   security requirement.

6. No `DemoStore` model exists anywhere in this app, deliberately --
   approved decision: live preview is a rendering MODE (Phase 13's
   storefront app, against a bundled fixture catalog), never a real
   tenant/Store row.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, TimeStampedModel
from apps.tenancy.models import TenantOwnedModel


class Theme(BaseModel, TimeStampedModel):
    """Global, code-linked identity -- the DB row is metadata pointing at
    a real theme package in the (future, Phase 13) storefront app, not a
    renderer itself."""

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "themes_theme"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.code


class ThemeVersion(BaseModel, TimeStampedModel):
    theme = models.ForeignKey("themes.Theme", on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    # The version new `StoreThemeConfig` provisioning uses when a preset
    # doesn't pin one explicitly. Never mutated on an EXISTING version --
    # publishing new contract terms creates a new ThemeVersion row and
    # flips this on the new one, in one transaction (mirrors
    # PlanVersion.is_current exactly).
    is_current = models.BooleanField(default=False)
    released_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "themes_themeversion"
        constraints = [
            models.UniqueConstraint(
                fields=["theme", "version_number"], name="uniq_version_number_per_theme"
            ),
            models.UniqueConstraint(
                fields=["theme"],
                condition=models.Q(is_current=True),
                name="uniq_current_version_per_theme",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.theme_id} v{self.version_number}"


class ThemePreset(BaseModel, TimeStampedModel):
    """A named, seeded starting point for `StoreThemeConfig.settings` --
    NOT a separate architectural concept from ThemeVersion, just default
    data + a preview image scoped to one. `preview_image_url` is a
    static asset in Phase 12 (approved decision); Phase 13 replaces the
    picker's preview with the real interactive renderer without needing
    any schema change here."""

    theme_version = models.ForeignKey(
        "themes.ThemeVersion", on_delete=models.CASCADE, related_name="presets"
    )
    name = models.CharField(max_length=255)
    default_settings = models.JSONField(default=dict)
    preview_image_url = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    # At most one ThemePreset is ever the automatic choice when
    # `apps.stores.services.create_store` isn't given an explicit one --
    # same "no Store may exist with no deterministic state" discipline
    # Phase 10 approved for the default trial Plan.
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "themes_themepreset"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="uniq_default_theme_preset",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class StoreThemeConfig(TenantOwnedModel):
    """One row per store, for the store's entire lifetime -- an explicit
    re-pin to a different ThemeVersion/preset moves THIS row, never
    creates a second one (`uniq_one_theme_config_per_store` below)."""

    theme_version = models.ForeignKey(
        "themes.ThemeVersion", on_delete=models.PROTECT, related_name="store_configs"
    )
    # Traceability only ("which preset did this start from") -- SET_NULL
    # on delete since presets are cosmetic reference data; deleting one
    # must never cascade-delete a store's live configuration.
    preset = models.ForeignKey(
        "themes.ThemePreset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="store_configs",
    )
    settings = models.JSONField(default=dict)

    class Meta:
        db_table = "themes_storethemeconfig"
        constraints = [
            models.UniqueConstraint(fields=["store"], name="uniq_one_theme_config_per_store"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"StoreThemeConfig({self.store_id})"
