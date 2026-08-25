from __future__ import annotations

from rest_framework import serializers

from apps.suppliers.models import Supplier, SupplierProduct
from apps.suppliers.pricing import compute_suggested_price


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "provider",
            "is_active",
            "pricing_strategy",
            "pricing_value",
            "min_profit_amount",
            "last_synced_at",
            "created_at",
        ]
        read_only_fields = ["id", "last_synced_at", "created_at"]


class SupplierProductSerializer(serializers.ModelSerializer):
    suggested_price_amount = serializers.SerializerMethodField()

    class Meta:
        model = SupplierProduct
        fields = [
            "id",
            "supplier",
            "external_id",
            "name",
            "cost_amount",
            "currency",
            "supplier_stock",
            "status",
            "imported_variant",
            "suggested_price_amount",
        ]
        read_only_fields = fields

    def get_suggested_price_amount(self, obj: SupplierProduct) -> int:
        supplier: Supplier = obj.supplier
        return compute_suggested_price(
            cost_amount=obj.cost_amount,
            strategy=supplier.pricing_strategy,
            value=supplier.pricing_value,
            min_profit_amount=supplier.min_profit_amount,
        )


class PromoteRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)
    sku = serializers.CharField(max_length=64)
    price_amount = serializers.IntegerField(min_value=0)
    location_id = serializers.UUIDField(required=False, allow_null=True)
    initial_stock = serializers.IntegerField(required=False, allow_null=True, min_value=0)
