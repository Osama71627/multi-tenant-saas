from __future__ import annotations

from rest_framework import serializers

from apps.carts.models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    # Real gap found live: the cart page only had `variant_sku` to show a
    # shopper what's in their cart -- a raw SKU string, never the actual
    # product name a shopper recognizes. Same `source="variant.X"` chain
    # pattern `variant_sku` already uses (this view's cart is a plain
    # fetched instance, not a queryset -- no select_related to add here
    # any more than the existing field already needed).
    product_name = serializers.CharField(source="variant.product.name", read_only=True)
    product_slug = serializers.CharField(source="variant.product.slug", read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant",
            "variant_sku",
            "product_name",
            "product_slug",
            "quantity",
            "unit_price_amount",
            "currency",
        ]
        read_only_fields = [
            "id",
            "variant_sku",
            "product_name",
            "product_slug",
            "unit_price_amount",
            "currency",
        ]


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
