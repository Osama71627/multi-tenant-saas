from django.urls import path

from apps.subscriptions.views import (
    CheckoutSessionCurrentView,
    PublicPlanListView,
    SubscriptionStatusView,
)

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/subscription",
        SubscriptionStatusView.as_view(),
        name="dashboard-store-subscription",
    ),
    # Phase D: public plan list + the authenticated user's checkout session.
    path("subscriptions/plans/public", PublicPlanListView.as_view(), name="public-plans"),
    path(
        "subscriptions/checkout-sessions/current",
        CheckoutSessionCurrentView.as_view(),
        name="checkout-session-current",
    ),
]
