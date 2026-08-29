"""
apps.subscriptions' HTTP surface -- Phase 12's first (read-only, for
now). Kept minimal on purpose: the dashboard's "subscription status" UI
needs a way to see what's already there; self-service upgrade/downgrade
over HTTP is real, deferred technical debt (docs/PHASE_10_REPORT.md),
not silently expanded here.

Phase D ("product vision reset" -- Plan Selection) adds the public plan
list and the authenticated checkout-session endpoints below.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.mixins import StoreScopedAPIView
from apps.subscriptions import billing, services
from apps.subscriptions.models import PlanVersion, Subscription
from apps.subscriptions.serializers import (
    BusinessInfoSerializer,
    CreatedStoreSerializer,
    InitiatePaymentSerializer,
    PublicPlanVersionSerializer,
    SelectPlanSerializer,
    StartSubscriptionCheckoutSessionSerializer,
    SubscriptionCheckoutSessionSerializer,
    SubscriptionPaymentIntentSerializer,
    SubscriptionStatusSerializer,
)


class SubscriptionStatusView(StoreScopedAPIView):
    @extend_schema(responses=SubscriptionStatusSerializer)
    def get(self, request: Request, store_id) -> Response:
        subscription = Subscription.objects.select_related("plan_version__plan").get(
            store=self.store
        )
        return Response(SubscriptionStatusSerializer(subscription).data)


class PublicPlanListView(APIView):
    """Phase D: the plan-selection screen's data source. Genuinely
    unauthenticated (`AllowAny`), matching `apps.themes`'s public
    theme-preset endpoints -- Plan/PlanVersion already carry an open
    RLS SELECT policy for everyone (Phase 10, approved architecture
    decision 1), so exposing the current public plans over HTTP adds
    no new write surface and leaks nothing merchant-specific."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PublicPlanVersionSerializer(many=True))
    def get(self, request: Request) -> Response:
        versions = (
            PlanVersion.objects.filter(is_current=True, plan__is_public=True)
            # The auto-assigned trial plan (apps.stores.services.create_store
            # -> provision_trial_subscription) is a different UI role from
            # "a plan a customer explicitly picks on a pricing screen" --
            # excluded here so it doesn't show up as a confusing $0 row
            # next to the real paid tiers. It's still is_public=True
            # because that flag genuinely means something else (RLS-
            # readable/eligible-for-normal-subscription-flows), not "show
            # on the plan-selection page".
            .exclude(plan__is_default_trial=True)
            .select_related("plan")
            .prefetch_related("features", "quotas")
            .order_by("price_monthly")
        )
        return Response(PublicPlanVersionSerializer(versions, many=True).data)


class CheckoutSessionCurrentView(APIView):
    """Phase D: the authenticated user's own in-progress checkout
    session, always resolved by `request.user` -- never a client-held
    session id (see `SubscriptionCheckoutSession`'s own docstring on
    why: the choice must survive a refresh or a fresh login exactly
    the same way, which a client-stored id could not guarantee if it
    were ever lost).

    GET returns the current session or 404 if none exists yet (a
    visitor who has picked neither a theme nor a plan). POST starts one
    (or updates the theme on an existing one) -- the marketplace's
    "Use this theme" flow. PATCH selects a plan on the existing session
    -- server-validated against real Plan/PlanVersion data, per
    `apps.subscriptions.services.select_plan_for_checkout_session`;
    the request body is a plan_version_id ONLY, never a price."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=SubscriptionCheckoutSessionSerializer)
    def get(self, request: Request) -> Response:
        session = services.get_active_checkout_session(user=request.user)
        if session is None:
            raise NotFound("No active checkout session for this user.")
        return Response(SubscriptionCheckoutSessionSerializer(session).data)

    @extend_schema(
        request=StartSubscriptionCheckoutSessionSerializer,
        responses=SubscriptionCheckoutSessionSerializer,
    )
    def post(self, request: Request) -> Response:
        body = StartSubscriptionCheckoutSessionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        session = services.start_or_update_checkout_session(
            user=request.user, theme_preset_id=body.validated_data.get("theme_preset_id")
        )
        return Response(SubscriptionCheckoutSessionSerializer(session).data)

    @extend_schema(request=SelectPlanSerializer, responses=SubscriptionCheckoutSessionSerializer)
    def patch(self, request: Request) -> Response:
        body = SelectPlanSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            session = services.select_plan_for_checkout_session(
                user=request.user, plan_version_id=body.validated_data["plan_version_id"]
            )
        except services.PlanVersionNotAvailableError as exc:
            return Response({"detail": str(exc)}, status=400)
        except services.NoActiveCheckoutSessionError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(SubscriptionCheckoutSessionSerializer(session).data)


class InitiatePaymentView(APIView):
    """Phase E: starts (or retries) a real, sandbox-provider-backed
    payment attempt -- gated by `settings.SUBSCRIPTION_BILLING_MODE`
    (see that setting's comment in config/settings/base.py). Creates a
    `SubscriptionPaymentIntent` and moves the session to
    `payment_pending`; the intent resolves asynchronously (a Celery task
    simulating the provider's own pending -> processing -> succeeded/
    failed callback, processed through the exact same idempotent
    webhook-handling code a real provider's callback would use -- see
    `apps.subscriptions.billing`). Never creates a Store."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=InitiatePaymentSerializer, responses=SubscriptionPaymentIntentSerializer)
    def post(self, request: Request) -> Response:
        body = InitiatePaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            intent = billing.initiate_payment(
                user=request.user, card_number=body.validated_data["card_number"]
            )
        except billing.BillingModeError as exc:
            return Response({"detail": str(exc)}, status=503)
        except billing.CheckoutNotPayableError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(SubscriptionPaymentIntentSerializer(intent).data, status=201)


class SkipPaymentDemoView(APIView):
    """DEMO-ONLY testing convenience, requested explicitly to speed up
    manual walkthroughs of the checkout flow: reaches
    `awaiting_business_info` without filling in the card form. Goes
    through the exact same state machine and idempotent
    `apply_payment_event` a real payment does (see
    `billing.skip_payment_demo`'s own docstring) -- this is NOT a
    bypass of Phase E's payment gate, it's a same-shaped payment that
    always succeeds synchronously instead of asynchronously. Gated by
    `SUBSCRIPTION_BILLING_MODE` exactly like `InitiatePaymentView`, so
    it is unreachable in production the same way."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=SubscriptionPaymentIntentSerializer)
    def post(self, request: Request) -> Response:
        try:
            intent = billing.skip_payment_demo(user=request.user)
        except billing.BillingModeError as exc:
            return Response({"detail": str(exc)}, status=503)
        except billing.CheckoutNotPayableError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(SubscriptionPaymentIntentSerializer(intent).data, status=201)


class PaymentIntentCurrentView(APIView):
    """Phase E: the authenticated user's most recent payment intent --
    polled by the checkout page while `state` is pending/processing,
    read once more for `failure_reason` on the failure screen. Scoped
    by `request.user` only, same "server-side, never a client-held id"
    posture as `CheckoutSessionCurrentView`."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=SubscriptionPaymentIntentSerializer)
    def get(self, request: Request) -> Response:
        intent = billing.get_active_intent(user=request.user)
        if intent is None:
            raise NotFound("No payment intent for this user yet.")
        return Response(SubscriptionPaymentIntentSerializer(intent).data)


class SubscriptionBillingWebhookView(APIView):
    """Phase E's real webhook endpoint -- the same idempotent,
    state-guarded `billing.apply_payment_event` this app's own demo-
    provider-simulation Celery task calls, reachable over HTTP the way
    a genuine provider callback would arrive. Deliberately `AllowAny`
    (a real webhook is never an authenticated user session) but hard-
    gated to `SUBSCRIPTION_BILLING_MODE == "demo"` -- there is no
    "live" signature verification implemented yet (see
    `apps.payments.services.process_webhook` for what that eventually
    needs to look like), so this must never be reachable in production
    regardless of URL discovery."""

    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        try:
            billing.require_demo_billing_mode()
        except billing.BillingModeError as exc:
            return Response({"detail": str(exc)}, status=503)

        intent_id = request.data.get("intent_id")
        external_id = request.data.get("external_id")
        kind = request.data.get("kind")
        if not intent_id or not external_id or not kind:
            return Response(
                {"detail": "intent_id, external_id, and kind are all required."}, status=400
            )
        billing.apply_payment_event(intent_id=intent_id, external_id=external_id, kind=kind)
        return Response(status=200)


class CheckoutSessionBusinessInfoView(APIView):
    """Phase F: the step that actually creates the Store. Requires a
    session already in `awaiting_business_info` (see
    `CheckoutSessionPayView`) -- `contact_email` is always
    `request.user.email`, never accepted from the client."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=BusinessInfoSerializer, responses=CreatedStoreSerializer)
    def post(self, request: Request) -> Response:
        body = BusinessInfoSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            store = services.complete_checkout_with_business_info(
                user=request.user,
                store_name=body.validated_data["store_name"],
                business_category=body.validated_data["business_category"],
                contact_phone=body.validated_data["contact_phone"],
                logo=body.validated_data.get("logo"),
            )
        except services.CheckoutNotAwaitingBusinessInfoError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(CreatedStoreSerializer(store).data, status=201)
