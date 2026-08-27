from django.urls import path

from apps.themes.views import (
    PublicThemePresetDetailView,
    PublicThemePresetListView,
    StorefrontContextView,
    StoreThemeConfigView,
    ThemePresetListView,
)

urlpatterns = [
    path("dashboard/theme-presets", ThemePresetListView.as_view(), name="dashboard-theme-presets"),
    path(
        "dashboard/stores/<uuid:store_id>/theme",
        StoreThemeConfigView.as_view(),
        name="dashboard-store-theme",
    ),
    path("storefront/context", StorefrontContextView.as_view(), name="storefront-context"),
    # Phase B: public theme marketplace -- genuinely unauthenticated,
    # see PublicThemePresetListView's own docstring for why.
    path(
        "themes/public/presets",
        PublicThemePresetListView.as_view(),
        name="public-theme-presets",
    ),
    path(
        "themes/public/presets/<uuid:preset_id>",
        PublicThemePresetDetailView.as_view(),
        name="public-theme-preset-detail",
    ),
]
