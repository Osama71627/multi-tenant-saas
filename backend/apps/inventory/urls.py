from django.urls import path

from apps.inventory import views

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/inventory/locations",
        views.StockLocationListCreateView.as_view(),
        name="inventory-location-list-create",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/inventory/balances",
        views.StockBalanceListView.as_view(),
        name="inventory-balance-list",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/inventory/adjust",
        views.AdjustStockView.as_view(),
        name="inventory-adjust",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/inventory/movements",
        views.StockMovementListView.as_view(),
        name="inventory-movement-list",
    ),
    path(
        "storefront/inventory/availability",
        views.StorefrontStockAvailabilityView.as_view(),
        name="storefront-inventory-availability",
    ),
]
