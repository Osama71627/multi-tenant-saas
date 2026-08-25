from __future__ import annotations

from rest_framework import serializers

from apps.orders.models import Order, OrderItem


class ShippingAddressSerializer(serializers.Serializer):
    """Validated JSONB snapshot shape -- see apps/orders/models.py's module docstring,
    decision 4 (no `CustomerAddress` model in Phase 8)."""

    recipient_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=32)
    country_code = serializers.CharField(max_length=2)
    region = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=255)
    postal_code = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    line1 = serializers.CharField(max_length=255)
    line2 = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class CheckoutAddressRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    shipping_address = ShippingAddressSerializer()


class CheckoutShippingRequestSerializer(serializers.Serializer):
    shipping_method_id = serializers.UUIDField()


class CheckoutSessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    email = serializers.EmailField(allow_blank=True)
    shipping_address = serializers.JSONField(allow_null=True)
    shipping_method_id = serializers.UUIDField(allow_null=True)
    shipping_method_name_snapshot = serializers.CharField(allow_blank=True)
    shipping_amount_snapshot = serializers.IntegerField(allow_null=True)


class OrderItemSerializer(serializers.ModelSerializer):
    line_total_amount = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant_name_snapshot",
            "variant_sku_snapshot",
            "variant_options_snapshot",
            "unit_price_amount",
            "quantity",
            "currency",
            "line_total_amount",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "email",
            "status",
            "fulfillment_status",
            "currency",
            "subtotal_amount",
            "discount_amount",
            "tax_amount",
            "shipping_amount",
            "total_amount",
            "shipping_address",
            "shipping_method_name_snapshot",
            "coupon_code_snapshot",
            "created_at",
            "items",
        ]


class OrderListSerializer(serializers.ModelSerializer):
    """Dashboard list view -- no `items` (avoids N+1 across a page of orders)."""

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "email",
            "status",
            "fulfillment_status",
            "currency",
            "total_amount",
            "created_at",
        ]
