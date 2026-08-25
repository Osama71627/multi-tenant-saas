"""
Theme provisioning. `provision_store_theme` is called from
`apps.stores.services.create_store`, inside that function's SAME atomic
transaction/tenant context (via `apps.stores.hooks`, registered from
`ThemesConfig.ready()`) -- approved Theme/Template decision: "no Store
may exist with no deterministic theme state", mirroring Phase 10's
identical rule for trial Subscription provisioning. If this raises
(e.g. `NoDefaultThemePresetError`, or an unknown/invalid `theme_preset_id`),
the whole transaction -- Store, StoreDomain, StoreMembership, trial
Subscription included -- rolls back; there is no "store exists, no theme
assigned" state, ever.
"""

from __future__ import annotations

import uuid

from apps.stores.models import Store
from apps.themes.models import StoreThemeConfig, ThemePreset
from apps.themes.schemas import validate_settings


class NoDefaultThemePresetError(Exception):
    """Raised if `ThemePreset.objects.get(is_default=True)` finds none --
    a deployment/seed-data precondition, not a user-facing error. See
    apps/themes/migrations/0002_seed_default_theme.py."""


class ThemePresetNotFoundError(Exception):
    """The caller supplied a `theme_preset_id` that doesn't exist or is
    inactive -- a real client error (invalid onboarding request), not a
    deployment gap."""


def get_default_theme_preset() -> ThemePreset:
    try:
        return ThemePreset.objects.select_related("theme_version__theme").get(
            is_default=True, is_active=True
        )
    except ThemePreset.DoesNotExist as exc:
        raise NoDefaultThemePresetError(
            "No ThemePreset has is_default=True -- the platform has no seeded "
            "default preset to provision new stores with."
        ) from exc


def resolve_theme_preset(*, theme_preset_id: uuid.UUID | str | None) -> ThemePreset:
    if theme_preset_id is None:
        return get_default_theme_preset()
    try:
        return ThemePreset.objects.select_related("theme_version__theme").get(
            id=theme_preset_id, is_active=True
        )
    except ThemePreset.DoesNotExist as exc:
        raise ThemePresetNotFoundError(
            f"No active ThemePreset with id={theme_preset_id!r}."
        ) from exc


def provision_store_theme(
    *, store: Store, theme_preset_id: uuid.UUID | str | None = None
) -> StoreThemeConfig:
    preset = resolve_theme_preset(theme_preset_id=theme_preset_id)
    theme_version = preset.theme_version
    validated_settings = validate_settings(
        theme_code=theme_version.theme.code,
        version_number=theme_version.version_number,
        data=preset.default_settings,
    )
    return StoreThemeConfig.objects.create(
        store=store,
        theme_version=theme_version,
        preset=preset,
        settings=validated_settings,
    )
