from django.urls import path

from apps.shipping import views

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/shipping/zones",
        views.ShippingZoneListCreateView.as_view(),
        name="shipping-zone-list-create",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/shipping/zones/<uuid:zone_id>/methods",
        views.ShippingMethodListCreateView.as_view(),
        name="shipping-method-list-create",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/shipping/methods/<uuid:method_id>/rates",
        views.ShippingRateListCreateView.as_view(),
        name="shipping-rate-list-create",
    ),
]
