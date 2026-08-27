"""Registers apps.themes TenantOwnedModels with the generic isolation test suite."""

from apps.tenancy.testing import register
from apps.themes.models import StoreThemeConfig
from apps.themes.services import get_default_theme_preset


@register(StoreThemeConfig)
def _store_theme_config_factory(store, suffix: str) -> StoreThemeConfig:
    # `ThemeVersion.objects.get(is_current=True)` (the old form here)
    # assumed exactly one ThemeVersion is ever `is_current=True`
    # platform-wide -- true only while Aurora was the sole theme.
    # `is_current` is actually scoped PER THEME (see
    # ThemeVersion.Meta's `uniq_current_version_per_theme` constraint),
    # so Phase B's 3 additional themes each having their own current
    # version made that bare `.get()` correctly raise
    # `MultipleObjectsReturned` -- caught by this session's own test
    # run, not assumed. `get_default_theme_preset()` is the real,
    # already-correct "the one true default" resolution every other
    # code path uses (apps.stores.services.create_store).
    theme_version = get_default_theme_preset().theme_version
    return StoreThemeConfig.objects.create(
        store=store,
        theme_version=theme_version,
        settings={"iso-suffix": suffix},
    )
