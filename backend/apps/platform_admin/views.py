"""Platform surface: `/api/v1/platform/...`. `TenantMiddleware` resolves
no tenant for this prefix by design (apps/stores/middleware.py) -- every
view here is cross-tenant by nature, gated purely by `IsPlatformStaff`,
never by `request.tenant_store` (which is always None here)."""

from __future__ import annotations

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PlatformUser
from apps.platform_admin import services
from apps.platform_admin.permissions import IsPlatformStaff
from apps.platform_admin.serializers import (
    AuditLogSerializer,
    PlanCreateRequestSerializer,
    PlanDetailSerializer,
    PlanSerializer,
    PlanVersionPublishRequestSerializer,
    PlanVersionSerializer,
    PlatformStoreSerializer,
    PlatformUserSerializer,
    StoreSuspendRequestSerializer,
    SubscriptionSerializer,
)
from apps.stores.models import Store
from apps.subscriptions.models import Plan, Subscription


class PlatformAPIView(APIView):
    permission_classes = [IsPlatformStaff]

    @property
    def platform_actor(self) -> PlatformUser:
        """`IsPlatformStaff` already guarantees `request.user` is an
        active, authenticated `PlatformUser` before any view method runs
        -- this just narrows the type for mypy (DRF's `Request.user` is
        typed as the union with `AnonymousUser`), same pattern as
        `apps.accounts.views.EmailVerifyResendView`'s explicit isinstance
        check."""
        user = self.request.user
        if not isinstance(user, PlatformUser):
            # pragma: no cover - unreachable given IsPlatformStaff
            raise exceptions.PermissionDenied
        return user


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


class PlatformOverviewView(PlatformAPIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        return Response(services.overview_metrics())


# --------------------------------------------------------------------------
# Stores
# --------------------------------------------------------------------------


def _get_store_or_404(store_id) -> Store:
    try:
        return services.get_store(store_id)
    except (Store.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class PlatformStoreListView(PlatformAPIView):
    @extend_schema(responses=PlatformStoreSerializer(many=True))
    def get(self, request: Request) -> Response:
        status_filter = request.query_params.get("status")
        stores = services.list_stores(status=status_filter)
        return Response(PlatformStoreSerializer(stores, many=True).data)


class PlatformStoreDetailView(PlatformAPIView):
    @extend_schema(responses=PlatformStoreSerializer)
    def get(self, request: Request, store_id) -> Response:
        store = _get_store_or_404(store_id)
        return Response(PlatformStoreSerializer(store).data)


class PlatformStoreSuspendView(PlatformAPIView):
    @extend_schema(request=StoreSuspendRequestSerializer, responses={200: PlatformStoreSerializer})
    def post(self, request: Request, store_id) -> Response:
        store = _get_store_or_404(store_id)
        serializer = StoreSuspendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = services.suspend_store(
            actor=self.platform_actor, store=store, reason=serializer.validated_data["reason"]
        )
        return Response(PlatformStoreSerializer(store).data)


class PlatformStoreActivateView(PlatformAPIView):
    @extend_schema(responses={200: PlatformStoreSerializer})
    def post(self, request: Request, store_id) -> Response:
        store = _get_store_or_404(store_id)
        store = services.activate_store(actor=self.platform_actor, store=store)
        return Response(PlatformStoreSerializer(store).data)


# --------------------------------------------------------------------------
# Plans / PlanVersions
# --------------------------------------------------------------------------


def _get_plan_or_404(plan_id) -> Plan:
    try:
        return services.get_plan(plan_id)
    except (Plan.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class PlatformPlanListCreateView(PlatformAPIView):
    @extend_schema(responses=PlanSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PlanSerializer(services.list_plans(), many=True).data)

    @extend_schema(request=PlanCreateRequestSerializer, responses={201: PlanSerializer})
    def post(self, request: Request) -> Response:
        serializer = PlanCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = services.create_plan(actor=self.platform_actor, **serializer.validated_data)
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlatformPlanDetailView(PlatformAPIView):
    @extend_schema(responses=PlanDetailSerializer)
    def get(self, request: Request, plan_id) -> Response:
        plan = _get_plan_or_404(plan_id)
        versions = services.list_plan_versions(plan=plan)
        data = PlanDetailSerializer(plan).data
        data["versions"] = PlanVersionSerializer(versions, many=True).data
        return Response(data)


class PlatformPlanVersionPublishView(PlatformAPIView):
    @extend_schema(
        request=PlanVersionPublishRequestSerializer, responses={201: PlanVersionSerializer}
    )
    def post(self, request: Request, plan_id) -> Response:
        plan = _get_plan_or_404(plan_id)
        serializer = PlanVersionPublishRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = services.publish_plan_version(
            actor=self.platform_actor, plan=plan, **serializer.validated_data
        )
        return Response(PlanVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class PlatformPlanActivateView(PlatformAPIView):
    @extend_schema(responses={200: PlanSerializer})
    def post(self, request: Request, plan_id) -> Response:
        plan = _get_plan_or_404(plan_id)
        plan = services.activate_plan(actor=self.platform_actor, plan=plan)
        return Response(PlanSerializer(plan).data)


class PlatformPlanDeactivateView(PlatformAPIView):
    @extend_schema(responses={200: PlanSerializer})
    def post(self, request: Request, plan_id) -> Response:
        plan = _get_plan_or_404(plan_id)
        plan = services.deactivate_plan(actor=self.platform_actor, plan=plan)
        return Response(PlanSerializer(plan).data)


# --------------------------------------------------------------------------
# Subscriptions
# --------------------------------------------------------------------------


def _get_subscription_or_404(subscription_id) -> Subscription:
    try:
        return services.get_subscription(subscription_id)
    except (Subscription.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class PlatformSubscriptionListView(PlatformAPIView):
    @extend_schema(responses=SubscriptionSerializer(many=True))
    def get(self, request: Request) -> Response:
        store_id = request.query_params.get("store_id")
        subscriptions = services.list_subscriptions(store_id=store_id)
        return Response(SubscriptionSerializer(subscriptions, many=True).data)


class PlatformSubscriptionDetailView(PlatformAPIView):
    @extend_schema(responses=SubscriptionSerializer)
    def get(self, request: Request, subscription_id) -> Response:
        subscription = _get_subscription_or_404(subscription_id)
        return Response(SubscriptionSerializer(subscription).data)


class PlatformSubscriptionActivateView(PlatformAPIView):
    @extend_schema(responses={200: SubscriptionSerializer})
    def post(self, request: Request, subscription_id) -> Response:
        subscription = _get_subscription_or_404(subscription_id)
        subscription = services.activate_subscription(
            actor=self.platform_actor, subscription=subscription
        )
        return Response(SubscriptionSerializer(subscription).data)


class PlatformSubscriptionCancelView(PlatformAPIView):
    @extend_schema(responses={200: SubscriptionSerializer})
    def post(self, request: Request, subscription_id) -> Response:
        subscription = _get_subscription_or_404(subscription_id)
        subscription = services.cancel_subscription(
            actor=self.platform_actor, subscription=subscription
        )
        return Response(SubscriptionSerializer(subscription).data)


# --------------------------------------------------------------------------
# Users (read-only)
# --------------------------------------------------------------------------


class PlatformUserListView(PlatformAPIView):
    @extend_schema(responses=PlatformUserSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PlatformUserSerializer(services.list_users(), many=True).data)


class PlatformUserDetailView(PlatformAPIView):
    @extend_schema(responses=PlatformUserSerializer)
    def get(self, request: Request, user_id) -> Response:
        try:
            user = services.get_user(user_id)
        except (PlatformUser.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc
        return Response(PlatformUserSerializer(user).data)


class PlatformUserMfaResetView(PlatformAPIView):
    """Explicit, audited privileged action -- see
    `services.reset_user_mfa`'s docstring for why this exists instead of
    any self-service MFA bypass."""

    @extend_schema(responses={204: None})
    def post(self, request: Request, user_id) -> Response:
        try:
            user = services.get_user(user_id)
        except (PlatformUser.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc
        services.reset_user_mfa(actor=self.platform_actor, user=user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Audit logs (read-only -- no mutation endpoint exists on purpose)
# --------------------------------------------------------------------------


class PlatformAuditLogListView(PlatformAPIView):
    @extend_schema(responses=AuditLogSerializer(many=True))
    def get(self, request: Request) -> Response:
        logs = services.list_audit_logs(
            target_type=request.query_params.get("target_type"),
            target_id=request.query_params.get("target_id"),
            store_id=request.query_params.get("store_id"),
        )
        return Response(AuditLogSerializer(logs, many=True).data)
