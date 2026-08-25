"""
Phase 16 -- Suppliers. Per docs/ARCHITECTURE.md section 10 ("بنية فقط في
v1"): interfaces + models + `MockSupplier` only, no real provider
integration in this phase. Roadmap DoD (section 15's table) is narrower
than that section's full sketch: "a complete mock import works", not a
purchase-order/procurement system -- so `SupplierOrder` (placing/
tracking a re-order WITH a supplier) is deliberately NOT built here.
Building an unused model with no service/view/test exercising it would
be exactly the kind of half-finished implementation this project avoids
everywhere else; the two-stage IMPORT path (Supplier -> SupplierProduct
staging -> explicit promotion to a real Product/Variant) is the whole
or Phase 16 slice, fully wired end to end.

`PriceRule` is also simplified from section 10's sketch: rather than a
separate table (implying multiple pricing rules per supplier, unused
complexity for an MVP where one supplier has one pricing policy), its
three fields (strategy/value/min_profit) live directly on `Supplier`.
See apps/suppliers/pricing.py for the calculation this feeds.

Both models are ordinary `TenantOwnedModel`s (store-scoped, standard
RLS) -- docs/ARCHITECTURE.md's own schema sketch already settles
"global vs per-store" in `Supplier`'s first field, `store`, matching
every other domain model in this project. No new tenancy pattern here.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantOwnedModel


class Supplier(TenantOwnedModel):
    class PricingStrategy(models.TextChoices):
        MARGIN_PERCENT = "margin_percent", "Margin %"
        MARKUP_PERCENT = "markup_percent", "Markup %"
        FIXED = "fixed", "Fixed price"

    class ProviderKey(models.TextChoices):
        MOCK = "mock", "Mock (demo data)"

    name = models.CharField(max_length=255)
    # Named `provider` (not `provider_key`) on purpose: apps.payments'
    # StoreProviderConfigCreateSerializer already declares a
    # `provider_key` ChoiceField with a DIFFERENT choice set, and
    # drf-spectacular names generated enums after the FIELD, not the
    # model -- two same-named fields with different choices collided
    # and got silently renamed with an unstable hash suffix, which broke
    # apps/storefront's generated `ProviderKeyEnum` reference at build
    # time (caught by `pnpm build`, not by any test). Different field
    # name sidesteps the collision entirely, no cross-app coordination
    # needed.
    provider = models.CharField(
        max_length=32, choices=ProviderKey.choices, default=ProviderKey.MOCK
    )
    is_active = models.BooleanField(default=True)

    # Suggested-selling-price policy applied when staging a
    # SupplierProduct for promotion -- see apps/suppliers/pricing.py.
    # The merchant can still override the suggested price by hand before
    # confirming the promotion; this is a default, not an enforced rule.
    pricing_strategy = models.CharField(
        max_length=16, choices=PricingStrategy.choices, default=PricingStrategy.MARKUP_PERCENT
    )
    # Percent (0-1000, for margin/markup strategies) or a fixed minor-units
    # amount (for the "fixed" strategy) -- meaning depends on pricing_strategy.
    pricing_value = models.PositiveIntegerField(default=50)
    min_profit_amount = models.PositiveIntegerField(
        default=0, help_text="Minor units. Suggested price never yields less profit than this."
    )

    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "suppliers_supplier"
        constraints = [
            models.UniqueConstraint(fields=["store", "name"], name="uniq_supplier_name_per_store"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class SupplierProduct(TenantOwnedModel):
    """
    One staged row per (supplier, external_id) -- a supplier's OWN
    catalog listing, not a real Product. `supplier_stock` is what the
    supplier claims to have, kept strictly as reference/staging data:
    apps.inventory remains the sole operational stock source of truth,
    and this field is never read by any inventory query -- only
    `promote()` (apps/suppliers/services.py) ever turns a number from
    here into a real stock movement, and only by calling
    apps.inventory.services.adjust_stock, never a direct balance write.
    """

    class Status(models.TextChoices):
        STAGED = "staged", "Staged"
        IMPORTED = "imported", "Imported"
        IGNORED = "ignored", "Ignored"

    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.CASCADE, related_name="products"
    )
    external_id = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    cost_amount = models.PositiveIntegerField(help_text="Minor units.")
    currency = models.CharField(max_length=3)
    supplier_stock = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STAGED)
    imported_variant = models.ForeignKey(
        "catalog.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "suppliers_supplierproduct"
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "external_id"], name="uniq_supplier_product_external_id"
            ),
        ]
        indexes = [models.Index(fields=["store", "supplier", "status"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.supplier_id}:{self.external_id})"
