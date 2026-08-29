from django.urls import path

from apps.subscriptions.views import (
    CheckoutSessionBusinessInfoView,
    CheckoutSessionCurrentView,
    InitiatePaymentView,
    PaymentIntentCurrentView,
    PublicPlanListView,
    SkipPaymentDemoView,
    SubscriptionBillingWebhookView,
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
    # Phase E.
    path(
        "subscriptions/checkout-sessions/current/pay",
        InitiatePaymentView.as_view(),
        name="checkout-session-pay",
    ),
    path(
        "subscriptions/checkout-sessions/current/payment-intent",
        PaymentIntentCurrentView.as_view(),
        name="checkout-session-payment-intent",
    ),
    # Demo-only testing convenience, not part of Phase E's required flow --
    # see SkipPaymentDemoView's own docstring.
    path(
        "subscriptions/checkout-sessions/current/skip-payment-demo",
        SkipPaymentDemoView.as_view(),
        name="checkout-session-skip-payment-demo",
    ),
    path(
        "subscriptions/billing/webhook",
        SubscriptionBillingWebhookView.as_view(),
        name="subscription-billing-webhook",
    ),
    # Phase F (already built, not part of Phase E's own flow -- see
    # apps/subscriptions/services.py's `complete_checkout_with_business_info`
    # docstring).
    path(
        "subscriptions/checkout-sessions/current/business-info",
        CheckoutSessionBusinessInfoView.as_view(),
        name="checkout-session-business-info",
    ),
]
