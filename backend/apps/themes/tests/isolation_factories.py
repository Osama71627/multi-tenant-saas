"""Registers apps.themes TenantOwnedModels with the generic isolation test suite."""

from apps.tenancy.testing import register
from apps.themes.models import StoreThemeConfig, ThemeVersion


@register(StoreThemeConfig)
def _store_theme_config_factory(store, suffix: str) -> StoreThemeConfig:
    theme_version = ThemeVersion.objects.get(is_current=True)
    return StoreThemeConfig.objects.create(
        store=store,
        theme_version=theme_version,
        settings={"iso-suffix": suffix},
    )
