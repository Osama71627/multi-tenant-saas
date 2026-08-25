from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
    Tag,
    VariantOptionValue,
)


class ProductOptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOptionValue
        fields = ["id", "value", "position"]
        read_only_fields = ["id", "position"]


class ProductOptionSerializer(serializers.ModelSerializer):
    values = ProductOptionValueSerializer(many=True, read_only=True)

    class Meta:
        model = ProductOption
        fields = ["id", "name", "position", "values"]
        read_only_fields = ["id", "position", "values"]


class VariantOptionValueSerializer(serializers.ModelSerializer):
    option_name = serializers.CharField(source="option.name", read_only=True)
    value = serializers.CharField(source="option_value.value", read_only=True)

    class Meta:
        model = VariantOptionValue
        fields = ["option_name", "value"]


class ProductVariantSerializer(serializers.ModelSerializer):
    option_values = VariantOptionValueSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "status",
            "is_default",
            "position",
            "currency",
            "price_amount",
            "compare_at_price_amount",
            "cost_price_amount",
            "weight_grams",
            "length_mm",
            "width_mm",
            "height_mm",
            "barcode",
            "option_values",
        ]
        read_only_fields = ["id", "is_default", "position", "option_values"]


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    options = ProductOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "status",
            "seo_title",
            "seo_description",
            "options",
            "variants",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "options", "variants", "created_at", "updated_at"]


class CreateProductSerializer(serializers.Serializer):
    """One-shot: Product + its default variant -- see apps/catalog/services.py:create_product."""

    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    seo_title = serializers.CharField(required=False, allow_blank=True, default="")
    seo_description = serializers.CharField(required=False, allow_blank=True, default="")
    sku = serializers.CharField(max_length=64)
    price_amount = serializers.IntegerField(min_value=0)
    currency = serializers.CharField(max_length=3, required=False)


class UpdateProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["name", "slug", "description", "status", "seo_title", "seo_description"]


class AddOptionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)


class AddOptionValueSerializer(serializers.Serializer):
    value = serializers.CharField(max_length=100)


class CreateVariantSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64)
    price_amount = serializers.IntegerField(min_value=0)
    currency = serializers.CharField(max_length=3, required=False)
    compare_at_price_amount = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    cost_price_amount = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    option_value_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "position"]
        read_only_fields = ["id"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]


# --------------------------------------------------------------------------
# Storefront (customer-facing) serializers -- Phase 13. Deliberately
# separate from the dashboard serializers above, not a shared base: the
# dashboard ones expose merchant-only data (`cost_price_amount`, draft/
# archived rows) that must never reach a shopper. Only `status="active"`
# products/variants are ever queried into these (enforced in the views).
# --------------------------------------------------------------------------


class StorefrontVariantOptionValueSerializer(serializers.ModelSerializer):
    option_name = serializers.CharField(source="option.name", read_only=True)
    value = serializers.CharField(source="option_value.value", read_only=True)

    class Meta:
        model = VariantOptionValue
        fields = ["option_name", "value"]


class StorefrontVariantSerializer(serializers.ModelSerializer):
    option_values = StorefrontVariantOptionValueSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "is_default",
            "position",
            "currency",
            "price_amount",
            "compare_at_price_amount",
            "weight_grams",
            "option_values",
        ]


class StorefrontProductListSerializer(serializers.ModelSerializer):
    """One row per product for grid/listing views. `price_amount`/
    `currency`/`compare_at_price_amount` come from the first active
    variant (by `position`) -- the view prefetches exactly that variant,
    ordered, so `.variants.all()[0]` never triggers a second query."""

    price_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    compare_at_price_amount = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "price_amount",
            "currency",
            "compare_at_price_amount",
        ]

    def _representative_variant(self, product: Product) -> ProductVariant | None:
        variants = list(product.variants.all())
        return variants[0] if variants else None

    def get_price_amount(self, product: Product) -> int | None:
        variant = self._representative_variant(product)
        return variant.price_amount if variant else None

    def get_currency(self, product: Product) -> str | None:
        variant = self._representative_variant(product)
        return variant.currency if variant else None

    def get_compare_at_price_amount(self, product: Product) -> int | None:
        variant = self._representative_variant(product)
        return variant.compare_at_price_amount if variant else None


class StorefrontProductDetailSerializer(serializers.ModelSerializer):
    variants = StorefrontVariantSerializer(many=True, read_only=True)
    options = ProductOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "seo_title",
            "seo_description",
            "options",
            "variants",
        ]


class StorefrontCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "position"]
