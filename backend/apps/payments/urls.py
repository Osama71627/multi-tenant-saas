from django.urls import path

from apps.payments import views

urlpatterns = [
    path(
        "storefront/payments/providers",
        views.StorefrontProviderListView.as_view(),
        name="storefront-payment-providers",
    ),
    path(
        "storefront/payments/initiate",
        views.PaymentInitiateView.as_view(),
        name="payment-initiate",
    ),
    path(
        "webhooks/payments/<str:provider>/<uuid:store_id>",
        views.PaymentWebhookView.as_view(),
        name="payment-webhook",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/payment-intents/<uuid:payment_intent_id>/capture-cod",
        views.ManualCodCaptureView.as_view(),
        name="payment-intent-capture-cod",
    ),
    path(
        "dashboard/stores/<uuid:store_id>/payments/providers",
        views.StoreProviderConfigListCreateView.as_view(),
        name="store-provider-config-list-create",
    ),
]
