from __future__ import annotations

from rest_framework import serializers

from apps.carts.models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "variant", "variant_sku", "quantity", "unit_price_amount", "currency"]
        read_only_fields = ["id", "variant_sku", "unit_price_amount", "currency"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    coupon_code = serializers.CharField(source="coupon.code", read_only=True, default=None)

    class Meta:
        model = Cart
        fields = [
            "id",
            "status",
            "currency",
            "items",
            "coupon_code",
            "subtotal_amount",
            "discount_amount",
            "tax_amount",
            "total_amount",
        ]
        read_only_fields = fields


class AddCartItemSerializer(serializers.Serializer):
    variant = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
