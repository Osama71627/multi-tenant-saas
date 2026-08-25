from django.urls import path

from apps.themes.views import StorefrontContextView, StoreThemeConfigView, ThemePresetListView

urlpatterns = [
    path("dashboard/theme-presets", ThemePresetListView.as_view(), name="dashboard-theme-presets"),
    path(
        "dashboard/stores/<uuid:store_id>/theme",
        StoreThemeConfigView.as_view(),
        name="dashboard-store-theme",
    ),
    path("storefront/context", StorefrontContextView.as_view(), name="storefront-context"),
]
