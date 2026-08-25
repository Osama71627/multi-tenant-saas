"""
Dashboard surface for Inventory, under
`/api/v1/dashboard/stores/<uuid:store_id>/inventory/...` -- every view
subclasses `StoreScopedAPIView` (apps/stores/mixins.py); see its
docstring for the membership-gating and 404-vs-403 reasoning.

Reservation/release/fulfill are deliberately NOT exposed as HTTP
endpoints yet -- there is no real caller (Cart/Checkout, Phase 6/8)
today, so building that surface now would be speculative API design
with no consumer to validate it against. The service functions
(apps/inventory/services.py) are fully built and tested; the HTTP
surface for them lands with whichever phase actually calls them.
"""

from __future__ import annotations

from django.db import IntegrityError
from django.db.models import F, Sum
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.catalog.models import ProductVariant
from apps.inventory import services
from apps.inventory.models import StockBalance, StockLocation, StockMovement
from apps.inventory.serializers import (
    AdjustStockSerializer,
    StockBalanceSerializer,
    StockLocationSerializer,
    StockMovementSerializer,
)
from apps.stores.mixins import StorefrontAPIView, StoreScopedAPIView


class StockLocationListCreateView(StoreScopedAPIView):
    @extend_schema(responses=StockLocationSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        return Response(StockLocationSerializer(StockLocation.objects.all(), many=True).data)

    @extend_schema(request=StockLocationSerializer, responses={201: StockLocationSerializer})
    def post(self, request: Request, store_id) -> Response:
        serializer = StockLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store)
        except IntegrityError:
            return Response(
                {"detail": "A location with this name already exists in this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StockBalanceListView(StoreScopedAPIView):
    @extend_schema(responses=StockBalanceSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        balances = StockBalance.objects.select_related("variant", "location").all()

        location_id = request.query_params.get("location")
        if location_id:
            balances = balances.filter(location_id=location_id)

        variant_id = request.query_params.get("variant")
        if variant_id:
            balances = balances.filter(variant_id=variant_id)

        rows = list(StockBalanceSerializer(balances, many=True).data)
        if request.query_params.get("low_stock") == "true":
            rows = [row for row in rows if row["is_low_stock"]]
        return Response(rows)


class AdjustStockView(StoreScopedAPIView):
    @extend_schema(request=AdjustStockSerializer, responses={200: StockBalanceSerializer})
    def post(self, request: Request, store_id) -> Response:
        serializer = AdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            variant = ProductVariant.objects.get(id=data["variant"])
        except (ProductVariant.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc
        try:
            location = StockLocation.objects.get(id=data["location"])
        except (StockLocation.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc

        try:
            balance = services.adjust_stock(
                store=self.store,
                variant=variant,
                location=location,
                delta=data["delta"],
                reason=data["reason"],
                reference=data["reference"],
            )
        except IntegrityError:
            # The `stockbalance_on_hand_non_negative` CHECK constraint --
            # the actual guard, not just this friendly message. Most
            # commonly: adjusting a balance below zero.
            return Response(
                {"detail": "This adjustment would take on-hand stock below zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StockBalanceSerializer(balance).data)


class StockMovementListView(StoreScopedAPIView):
    def get(self, request: Request, store_id) -> Response:
        movements = StockMovement.objects.all()

        reference = request.query_params.get("reference")
        if reference:
            movements = movements.filter(reference=reference)

        variant_id = request.query_params.get("variant")
        if variant_id:
            movements = movements.filter(variant_id=variant_id)

        return Response(StockMovementSerializer(movements, many=True).data)


class StorefrontStockAvailabilityView(StorefrontAPIView):
    """`GET .../storefront/inventory/availability?variant=<id>&variant=<id>` --
    Phase 13. Only ever returns a summed "available across all locations"
    integer per variant, never per-location detail or any other
    `StockBalance` field -- that breakdown is a merchant-only concept.
    An id with no `StockBalance` rows at all is simply absent from the
    response (zero-available and never-stocked look the same to a
    shopper: not orderable)."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "variant",
                str,
                required=False,
                many=True,
                description="Repeatable -- one or more ProductVariant ids.",
            )
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request) -> Response:
        variant_ids = request.query_params.getlist("variant")
        if not variant_ids:
            return Response({})

        rows = (
            StockBalance.objects.filter(variant_id__in=variant_ids)
            .values("variant_id")
            .annotate(available=Sum(F("quantity_on_hand") - F("quantity_reserved")))
        )
        return Response({str(row["variant_id"]): row["available"] for row in rows})
