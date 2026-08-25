from django.urls import path

from apps.carts import views

urlpatterns = [
    path("storefront/cart", views.CartDetailView.as_view(), name="storefront-cart-detail"),
    path(
        "storefront/cart/items",
        views.CartItemListCreateView.as_view(),
        name="storefront-cart-item-list-create",
    ),
    path(
        "storefront/cart/items/<uuid:item_id>",
        views.CartItemDetailView.as_view(),
        name="storefront-cart-item-detail",
    ),
    path("storefront/cart/coupon", views.CartCouponView.as_view(), name="storefront-cart-coupon"),
    path(
        "storefront/cart/reprice", views.CartRepriceView.as_view(), name="storefront-cart-reprice"
    ),
    path(
        "storefront/cart/shipping-quotes",
        views.CartShippingQuotesView.as_view(),
        name="storefront-cart-shipping-quotes",
    ),
]
