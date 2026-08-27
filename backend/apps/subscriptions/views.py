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
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.mixins import StoreScopedAPIView
from apps.subscriptions import services
from apps.subscriptions.models import PlanVersion, Subscription
from apps.subscriptions.serializers import (
    PublicPlanVersionSerializer,
    SelectPlanSerializer,
    StartSubscriptionCheckoutSessionSerializer,
    SubscriptionCheckoutSessionSerializer,
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
