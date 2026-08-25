"""
Product catalog. Architecture decisions locked in for Phase 4 (see
docs/PHASE_4_REPORT.md for the full record):

1. EVERY `Product` has at least one `ProductVariant` -- SKU, price,
   weight etc. live ONLY on `ProductVariant`, never on `Product`. A
   "simple" product (no real options) gets exactly one variant with
   `is_default=True`. This keeps every future consumer (Cart, Inventory,
   Orders) pointed at a single, unambiguous "the thing being sold"
   concept: a variant id, never a product-or-variant branch.

2. Option/value storage is fully normalized (`ProductOption` ->
   `ProductOptionValue` -> `VariantOptionValue`), NOT JSON on the
   variant. Options are Product-scoped, not a store-wide/global catalog.

3. `ProductVariant` carries ZERO inventory quantity state (no
   `stock_quantity`, no `available_quantity`, nothing). Catalog defines
   WHAT is sellable; Phase 8 (Inventory) will own HOW MANY exist, as its
   own table referencing `ProductVariant` by FK. Never conflate the two
   bounded contexts.

Two uniqueness rules are enforced with genuine DB constraints, not just
Python validation (required per docs/PHASE_3_REPORT.md's RLS lesson AND
this phase's explicit governance):

  * One value per option per variant: `VariantOptionValue`'s
    `UniqueConstraint(["variant", "option"])`.
  * No duplicate option-value COMBINATION within the same product: this
    is a "no two rows share the same subset of a many-to-many" rule,
    which Postgres can't express as a plain per-row constraint on the
    through table. `ProductVariant.option_signature` (a sorted array of
    the selected `ProductOptionValue` ids, maintained by
    apps/catalog/services.py alongside the relational
    `VariantOptionValue` rows in the same transaction) turns it into an
    ordinary column equality check: `UniqueConstraint(["product",
    "option_signature"])`. Verified directly against PostgreSQL that a
    UNIQUE index on a uuid[] column works and rejects duplicates before
    relying on it (docs/PHASE_4_REPORT.md).
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.tenancy.models import TenantOwnedModel


class Product(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "catalog_product"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="uniq_product_slug_per_store"),
        ]
        indexes = [models.Index(fields=["store", "status"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class ProductOption(TenantOwnedModel):
    """E.g. "Size" or "Color" -- product-scoped, not a store-wide catalog (Phase 4 decision)."""

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_productoption"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"], name="uniq_option_name_per_product"
            ),
        ]
        ordering = ["position", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class ProductOptionValue(TenantOwnedModel):
    """E.g. "M" / "Red" under the "Size" / "Color" option."""

    option = models.ForeignKey(
        "catalog.ProductOption", on_delete=models.CASCADE, related_name="values"
    )
    value = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_productoptionvalue"
        constraints = [
            models.UniqueConstraint(
                fields=["option", "value"], name="uniq_option_value_per_option"
            ),
        ]
        ordering = ["position", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ProductVariant(TenantOwnedModel):
    """
    The actual sellable unit -- SKU, price, weight all live here, never
    on `Product`. See this module's docstring for why, and for the
    `option_signature` uniqueness mechanism.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_default = models.BooleanField(
        default=False,
        help_text="True only for the auto-created variant of a simple (option-less) product.",
    )
    position = models.PositiveIntegerField(default=0)

    # Money: integer minor units + explicit currency per record, never
    # floating point -- docs/DECISIONS.md governance point 4.
    currency = models.CharField(max_length=3)
    price_amount = models.PositiveIntegerField()
    compare_at_price_amount = models.PositiveIntegerField(null=True, blank=True)
    cost_price_amount = models.PositiveIntegerField(null=True, blank=True)

    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    length_mm = models.PositiveIntegerField(null=True, blank=True)
    width_mm = models.PositiveIntegerField(null=True, blank=True)
    height_mm = models.PositiveIntegerField(null=True, blank=True)
    barcode = models.CharField(max_length=64, blank=True)

    # DB-enforced "no duplicate option-value combination per product" --
    # sorted ProductOptionValue ids selected for this variant, kept in
    # sync with the relational `VariantOptionValue` rows by
    # apps/catalog/services.py in the same transaction. Empty list for a
    # simple product's default variant (no options at all).
    option_signature = ArrayField(models.UUIDField(), default=list, blank=True)

    class Meta:
        db_table = "catalog_productvariant"
        constraints = [
            models.UniqueConstraint(fields=["store", "sku"], name="uniq_variant_sku_per_store"),
            models.UniqueConstraint(
                fields=["product", "option_signature"],
                name="uniq_variant_option_combo_per_product",
            ),
        ]
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["store", "status"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.sku


class VariantOptionValue(TenantOwnedModel):
    """
    Relational (queryable) record of "this variant's Size is M" --
    `option` is denormalized from `option_value.option` purely so a
    plain DB `UniqueConstraint(["variant", "option"])` can enforce "one
    value per option per variant" without a cross-table constraint.
    """

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="option_values"
    )
    option = models.ForeignKey("catalog.ProductOption", on_delete=models.CASCADE, related_name="+")
    option_value = models.ForeignKey(
        "catalog.ProductOptionValue", on_delete=models.CASCADE, related_name="+"
    )

    class Meta:
        db_table = "catalog_variantoptionvalue"
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "option"], name="uniq_one_value_per_option_per_variant"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.variant_id}: {self.option_id}={self.option_value_id}"


class Category(TenantOwnedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_category"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="uniq_category_slug_per_store"),
        ]
        ordering = ["position", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class ProductCategory(TenantOwnedModel):
    """M2M through table -- tenant-scoped/RLS-protected like every table here (Phase 4 rule)."""

    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="product_categories"
    )
    category = models.ForeignKey(
        "catalog.Category", on_delete=models.CASCADE, related_name="product_categories"
    )

    class Meta:
        db_table = "catalog_productcategory"
        constraints = [
            models.UniqueConstraint(fields=["product", "category"], name="uniq_product_category"),
        ]


class Tag(TenantOwnedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)

    class Meta:
        db_table = "catalog_tag"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="uniq_tag_slug_per_store"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class ProductTag(TenantOwnedModel):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="product_tags"
    )
    tag = models.ForeignKey("catalog.Tag", on_delete=models.CASCADE, related_name="product_tags")

    class Meta:
        db_table = "catalog_producttag"
        constraints = [
            models.UniqueConstraint(fields=["product", "tag"], name="uniq_product_tag"),
        ]


class ProductImage(TenantOwnedModel):
    """
    URL-only for now -- no upload/storage infrastructure exists in this
    project yet (S3/MinIO was never set up). Modeling the shape now is
    not scope creep; building upload processing would be.
    """

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="images")
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="images",
    )
    url = models.URLField(max_length=1000)
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_productimage"
        ordering = ["position", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.url
