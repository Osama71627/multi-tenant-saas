"""Dashboard surface for shipping zones/methods/rates, under
`.../dashboard/stores/<uuid:store_id>/shipping/...`."""

from __future__ import annotations

from django.db import IntegrityError
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.shipping.models import ShippingMethod, ShippingRate, ShippingZone
from apps.shipping.serializers import (
    ShippingMethodSerializer,
    ShippingRateSerializer,
    ShippingZoneSerializer,
)
from apps.stores.mixins import StoreScopedAPIView


def _get_zone_or_404(zone_id) -> ShippingZone:
    try:
        return ShippingZone.objects.get(id=zone_id)
    except (ShippingZone.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


def _get_method_or_404(method_id) -> ShippingMethod:
    try:
        return ShippingMethod.objects.get(id=method_id)
    except (ShippingMethod.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class ShippingZoneListCreateView(StoreScopedAPIView):
    @extend_schema(responses=ShippingZoneSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        return Response(ShippingZoneSerializer(ShippingZone.objects.all(), many=True).data)

    @extend_schema(request=ShippingZoneSerializer, responses={201: ShippingZoneSerializer})
    def post(self, request: Request, store_id) -> Response:
        serializer = ShippingZoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(store=self.store)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShippingMethodListCreateView(StoreScopedAPIView):
    @extend_schema(responses=ShippingMethodSerializer(many=True))
    def get(self, request: Request, store_id, zone_id) -> Response:
        zone = _get_zone_or_404(zone_id)
        return Response(
            ShippingMethodSerializer(ShippingMethod.objects.filter(zone=zone), many=True).data
        )

    @extend_schema(request=ShippingMethodSerializer, responses={201: ShippingMethodSerializer})
    def post(self, request: Request, store_id, zone_id) -> Response:
        zone = _get_zone_or_404(zone_id)
        serializer = ShippingMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(store=self.store, zone=zone)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShippingRateListCreateView(StoreScopedAPIView):
    @extend_schema(responses=ShippingRateSerializer(many=True))
    def get(self, request: Request, store_id, method_id) -> Response:
        method = _get_method_or_404(method_id)
        return Response(
            ShippingRateSerializer(ShippingRate.objects.filter(method=method), many=True).data
        )

    @extend_schema(request=ShippingRateSerializer, responses={201: ShippingRateSerializer})
    def post(self, request: Request, store_id, method_id) -> Response:
        method = _get_method_or_404(method_id)
        serializer = ShippingRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store, method=method)
        except IntegrityError:
            return Response(
                {"detail": "This rate's max_value is below its min_value."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
