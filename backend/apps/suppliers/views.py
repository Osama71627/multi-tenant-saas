"""Dashboard surface: `/api/v1/dashboard/stores/<uuid:store_id>/suppliers/...`."""

from __future__ import annotations

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.inventory.models import StockLocation
from apps.stores.mixins import StoreScopedAPIView
from apps.suppliers import services
from apps.suppliers.models import Supplier, SupplierProduct
from apps.suppliers.serializers import (
    PromoteRequestSerializer,
    SupplierProductSerializer,
    SupplierSerializer,
)
from apps.suppliers.services import AlreadyImportedError


def _get_supplier_or_404(supplier_id) -> Supplier:
    try:
        return Supplier.objects.get(id=supplier_id)
    except (Supplier.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


def _get_supplier_product_or_404(supplier_product_id) -> SupplierProduct:
    try:
        return SupplierProduct.objects.select_related("supplier").get(id=supplier_product_id)
    except (SupplierProduct.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class SupplierListCreateView(StoreScopedAPIView):
    @extend_schema(responses=SupplierSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        return Response(SupplierSerializer(Supplier.objects.all(), many=True).data)

    @extend_schema(request=SupplierSerializer, responses={201: SupplierSerializer})
    def post(self, request: Request, store_id) -> Response:
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = Supplier.objects.create(store=self.store, **serializer.validated_data)
        return Response(SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED)


class SupplierSyncView(StoreScopedAPIView):
    @extend_schema(responses={200: SupplierProductSerializer(many=True)})
    def post(self, request: Request, store_id, supplier_id) -> Response:
        supplier = _get_supplier_or_404(supplier_id)
        staged = services.sync_supplier_catalog(store=self.store, supplier=supplier)
        return Response(SupplierProductSerializer(staged, many=True).data)


class SupplierProductListView(StoreScopedAPIView):
    @extend_schema(responses=SupplierProductSerializer(many=True))
    def get(self, request: Request, store_id, supplier_id) -> Response:
        supplier = _get_supplier_or_404(supplier_id)
        products = SupplierProduct.objects.filter(supplier=supplier)
        status_filter = request.query_params.get("status")
        if status_filter:
            products = products.filter(status=status_filter)
        return Response(SupplierProductSerializer(products, many=True).data)


class SupplierProductPromoteView(StoreScopedAPIView):
    @extend_schema(request=PromoteRequestSerializer, responses={201: dict})
    def post(self, request: Request, store_id, supplier_product_id) -> Response:
        supplier_product = _get_supplier_product_or_404(supplier_product_id)
        serializer = PromoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        location = None
        if data.get("location_id"):
            try:
                location = StockLocation.objects.get(id=data["location_id"])
            except StockLocation.DoesNotExist as exc:
                raise Http404 from exc

        try:
            product = services.promote_supplier_product(
                store=self.store,
                supplier_product=supplier_product,
                name=data["name"],
                slug=data["slug"],
                sku=data["sku"],
                price_amount=data["price_amount"],
                location=location,
                initial_stock=data.get("initial_stock"),
            )
        except AlreadyImportedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"product_id": str(product.id)}, status=status.HTTP_201_CREATED)
