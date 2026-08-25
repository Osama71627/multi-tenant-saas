"""Dashboard surface for tax rates and coupons, under `.../stores/<uuid:store_id>/pricing/...`."""

from __future__ import annotations

from django.db import IntegrityError
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.pricing.models import Coupon, TaxRate
from apps.pricing.serializers import CouponSerializer, TaxRateSerializer
from apps.stores.mixins import StoreScopedAPIView


class TaxRateListCreateView(StoreScopedAPIView):
    def get(self, request: Request, store_id) -> Response:
        return Response(TaxRateSerializer(TaxRate.objects.all(), many=True).data)

    def post(self, request: Request, store_id) -> Response:
        serializer = TaxRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store)
        except IntegrityError:
            return Response(
                {
                    "detail": "This store already has an active tax rate -- "
                    "deactivate it before adding another."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CouponListCreateView(StoreScopedAPIView):
    def get(self, request: Request, store_id) -> Response:
        return Response(CouponSerializer(Coupon.objects.all(), many=True).data)

    def post(self, request: Request, store_id) -> Response:
        serializer = CouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store)
        except IntegrityError:
            return Response(
                {"detail": "A coupon with this code already exists in this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
