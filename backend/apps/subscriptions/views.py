"""
apps.subscriptions' HTTP surface -- Phase 12's first (read-only, for
now). Kept minimal on purpose: the dashboard's "subscription status" UI
needs a way to see what's already there; self-service upgrade/downgrade
over HTTP is real, deferred technical debt (docs/PHASE_10_REPORT.md),
not silently expanded here.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from apps.stores.mixins import StoreScopedAPIView
from apps.subscriptions.models import Subscription
from apps.subscriptions.serializers import SubscriptionStatusSerializer


class SubscriptionStatusView(StoreScopedAPIView):
    @extend_schema(responses=SubscriptionStatusSerializer)
    def get(self, request: Request, store_id) -> Response:
        subscription = Subscription.objects.select_related("plan_version__plan").get(
            store=self.store
        )
        return Response(SubscriptionStatusSerializer(subscription).data)
