"""Dashboard surface: `/api/v1/dashboard/stores/<uuid:store_id>/analytics/...`."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from apps.analytics import services
from apps.stores.mixins import StoreScopedAPIView


class StoreAnalyticsOverviewView(StoreScopedAPIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request, store_id) -> Response:
        return Response(services.store_overview_metrics(store=self.store))
