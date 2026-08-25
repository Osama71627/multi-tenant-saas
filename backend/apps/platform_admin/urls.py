from django.urls import path

from apps.platform_admin import views

urlpatterns = [
    path("platform/overview", views.PlatformOverviewView.as_view(), name="platform-overview"),
    path("platform/stores", views.PlatformStoreListView.as_view(), name="platform-store-list"),
    path(
        "platform/stores/<uuid:store_id>",
        views.PlatformStoreDetailView.as_view(),
        name="platform-store-detail",
    ),
    path(
        "platform/stores/<uuid:store_id>/suspend",
        views.PlatformStoreSuspendView.as_view(),
        name="platform-store-suspend",
    ),
    path(
        "platform/stores/<uuid:store_id>/activate",
        views.PlatformStoreActivateView.as_view(),
        name="platform-store-activate",
    ),
    path(
        "platform/plans",
        views.PlatformPlanListCreateView.as_view(),
        name="platform-plan-list-create",
    ),
    path(
        "platform/plans/<uuid:plan_id>",
        views.PlatformPlanDetailView.as_view(),
        name="platform-plan-detail",
    ),
    path(
        "platform/plans/<uuid:plan_id>/versions",
        views.PlatformPlanVersionPublishView.as_view(),
        name="platform-plan-version-publish",
    ),
    path(
        "platform/plans/<uuid:plan_id>/activate",
        views.PlatformPlanActivateView.as_view(),
        name="platform-plan-activate",
    ),
    path(
        "platform/plans/<uuid:plan_id>/deactivate",
        views.PlatformPlanDeactivateView.as_view(),
        name="platform-plan-deactivate",
    ),
    path(
        "platform/subscriptions",
        views.PlatformSubscriptionListView.as_view(),
        name="platform-subscription-list",
    ),
    path(
        "platform/subscriptions/<uuid:subscription_id>",
        views.PlatformSubscriptionDetailView.as_view(),
        name="platform-subscription-detail",
    ),
    path(
        "platform/subscriptions/<uuid:subscription_id>/activate",
        views.PlatformSubscriptionActivateView.as_view(),
        name="platform-subscription-activate",
    ),
    path(
        "platform/subscriptions/<uuid:subscription_id>/cancel",
        views.PlatformSubscriptionCancelView.as_view(),
        name="platform-subscription-cancel",
    ),
    path("platform/users", views.PlatformUserListView.as_view(), name="platform-user-list"),
    path(
        "platform/users/<uuid:user_id>",
        views.PlatformUserDetailView.as_view(),
        name="platform-user-detail",
    ),
    path(
        "platform/users/<uuid:user_id>/mfa/reset",
        views.PlatformUserMfaResetView.as_view(),
        name="platform-user-mfa-reset",
    ),
    path(
        "platform/audit-logs",
        views.PlatformAuditLogListView.as_view(),
        name="platform-audit-log-list",
    ),
]
