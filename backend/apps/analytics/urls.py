from django.urls import path

from apps.analytics import views

urlpatterns = [
    path(
        "dashboard/stores/<uuid:store_id>/analytics/overview",
        views.StoreAnalyticsOverviewView.as_view(),
        name="store-analytics-overview",
    ),
]
