from django.urls import path

from apps.orders import views

urlpatterns = [
    path("storefront/checkout/start", views.CheckoutStartView.as_view(), name="checkout-start"),
    path(
        "storefront/checkout/address",
        views.CheckoutAddressView.as_view(),
        name="checkout-address",
    ),
    path(
        "storefront/checkout/shipping",
        views.CheckoutShippingView.as_view(),
        name="checkout-shipping",
    ),
    path(
        "storefront/checkout/complete",
        views.CheckoutCompleteView.as_view(),
        name="checkout-complete",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/orders",
        views.OrderListView.as_view(),
        name="order-list",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/orders/<uuid:order_id>",
        views.OrderDetailView.as_view(),
        name="order-detail",
    ),
]
