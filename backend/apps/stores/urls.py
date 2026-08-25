from django.urls import path

from apps.stores.views import StoreDetailView, StoreListCreateView

urlpatterns = [
    path("dashboard/stores", StoreListCreateView.as_view(), name="dashboard-store-list-create"),
    path(
        "dashboard/stores/<uuid:store_id>",
        StoreDetailView.as_view(),
        name="dashboard-store-detail",
    ),
]
