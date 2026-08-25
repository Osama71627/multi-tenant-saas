from __future__ import annotations

from rest_framework import serializers

from apps.pricing.models import Coupon, TaxRate


class TaxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRate
        fields = [
            "id",
            "name",
            "country_code",
            "region",
            "rate_percent",
            "is_active",
            "effective_from",
            "effective_to",
        ]
        read_only_fields = ["id"]


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "kind",
            "percentage_value",
            "fixed_amount_value",
            "currency",
            "is_active",
            "starts_at",
            "ends_at",
            "usage_limit",
            "times_used",
        ]
        read_only_fields = ["id", "times_used"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        percentage_value = attrs.get("percentage_value")
        fixed_amount_value = attrs.get("fixed_amount_value")
        currency = attrs.get("currency", getattr(self.instance, "currency", ""))

        if kind == Coupon.Kind.PERCENTAGE:
            if not percentage_value:
                raise serializers.ValidationError(
                    {"percentage_value": "Required for a percentage coupon."}
                )
            if fixed_amount_value:
                raise serializers.ValidationError(
                    {"fixed_amount_value": "Must be empty for a percentage coupon."}
                )
        elif kind == Coupon.Kind.FIXED_AMOUNT:
            if not fixed_amount_value:
                raise serializers.ValidationError(
                    {"fixed_amount_value": "Required for a fixed-amount coupon."}
                )
            if percentage_value:
                raise serializers.ValidationError(
                    {"percentage_value": "Must be empty for a fixed-amount coupon."}
                )
            if not currency:
                raise serializers.ValidationError(
                    {"currency": "Required for a fixed-amount coupon."}
                )
        return attrs

    def validate_code(self, value: str) -> str:
        return value.strip().upper()
