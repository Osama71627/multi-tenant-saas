from __future__ import annotations

from rest_framework import serializers

from apps.inventory.models import StockBalance, StockLocation, StockMovement


class StockLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockLocation
        fields = ["id", "name", "is_active"]
        read_only_fields = ["id"]


class StockBalanceSerializer(serializers.ModelSerializer):
    quantity_available = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = StockBalance
        fields = [
            "id",
            "variant",
            "variant_sku",
            "location",
            "location_name",
            "quantity_on_hand",
            "quantity_reserved",
            "quantity_available",
            "low_stock_threshold",
            "is_low_stock",
        ]
        read_only_fields = [
            "id",
            "variant_sku",
            "location_name",
            "quantity_on_hand",
            "quantity_reserved",
            "quantity_available",
            "is_low_stock",
        ]


class AdjustStockSerializer(serializers.Serializer):
    variant = serializers.UUIDField()
    location = serializers.UUIDField()
    delta = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)
    reference = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "variant",
            "location",
            "kind",
            "delta_on_hand",
            "delta_reserved",
            "balance_on_hand_after",
            "balance_reserved_after",
            "reference",
            "reason",
            "created_at",
        ]
        read_only_fields = fields
