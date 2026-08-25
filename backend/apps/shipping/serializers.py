from __future__ import annotations

from rest_framework import serializers

from apps.shipping.models import ShippingMethod, ShippingRate, ShippingZone


class ShippingZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingZone
        fields = [
            "id",
            "name",
            "countries",
            "regions",
            "postal_patterns",
            "priority",
            "is_active",
        ]
        read_only_fields = ["id"]


class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = ["id", "zone", "name", "kind", "is_active", "position"]
        read_only_fields = ["id"]


class ShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRate
        fields = ["id", "method", "min_value", "max_value", "price_amount", "currency"]
        read_only_fields = ["id"]


class ShippingQuoteRequestSerializer(serializers.Serializer):
    country_code = serializers.CharField(max_length=2)
    region = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


class ShippingQuoteSerializer(serializers.Serializer):
    method_id = serializers.UUIDField()
    method_name = serializers.CharField()
    kind = serializers.CharField()
    price_amount = serializers.IntegerField()
    currency = serializers.CharField()
