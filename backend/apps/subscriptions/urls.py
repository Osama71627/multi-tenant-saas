from django.urls import path

from apps.subscriptions.views import SubscriptionStatusView

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/subscription",
        SubscriptionStatusView.as_view(),
        name="dashboard-store-subscription",
    ),
]
