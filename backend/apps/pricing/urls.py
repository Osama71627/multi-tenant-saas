from django.urls import path

from apps.pricing import views

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/pricing/tax-rates",
        views.TaxRateListCreateView.as_view(),
        name="pricing-tax-rate-list-create",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/pricing/coupons",
        views.CouponListCreateView.as_view(),
        name="pricing-coupon-list-create",
    ),
]
