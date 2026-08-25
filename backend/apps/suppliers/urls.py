from django.urls import path

from apps.suppliers import views

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/suppliers",
        views.SupplierListCreateView.as_view(),
        name="supplier-list-create",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/suppliers/<uuid:supplier_id>/sync",
        views.SupplierSyncView.as_view(),
        name="supplier-sync",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/suppliers/<uuid:supplier_id>/products",
        views.SupplierProductListView.as_view(),
        name="supplier-product-list",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/supplier-products/<uuid:supplier_product_id>/promote",
        views.SupplierProductPromoteView.as_view(),
        name="supplier-product-promote",
    ),
]
