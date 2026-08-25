"""
Tax and discount configuration. Deliberately store-scoped only, with NO
dependency on apps.catalog -- Phase 6 doesn't need per-product tax/
discount rules (original spec: a single cart-level coupon; VAT
configurable per merchant, not per product), so this app stays a pure
calculation layer apps.carts consumes, not the other way around.

Money: integer minor units, explicit currency, never floating point
(docs/DECISIONS.md governance point 4) -- same as apps.catalog.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantOwnedModel


class TaxRate(TenantOwnedModel):
    """
    NOT hardcoded VAT (docs/DECISIONS.md governance point 5) -- a
    merchant configures their own rate. `country_code`/`region` are
    recorded for the merchant's own record-keeping and for a future
    destination-based lookup (once Checkout has a real shipping address
    to match against, Phase 8) -- Phase 6's calculator does not use them
    for selection, it just uses "the store's one active rate", enforced
    by the partial unique constraint below rather than left ambiguous.
    """

    name = models.CharField(max_length=255)
    country_code = models.CharField(max_length=2, help_text="ISO 3166-1 alpha-2, e.g. 'SA'.")
    region = models.CharField(max_length=255, blank=True)
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "pricing_taxrate"
        constraints = [
            models.UniqueConstraint(
                fields=["store"],
                condition=models.Q(is_active=True),
                name="uniq_one_active_taxrate_per_store",
            ),
            models.CheckConstraint(
                condition=models.Q(rate_percent__gte=0) & models.Q(rate_percent__lte=100),
                name="taxrate_rate_percent_in_range",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.rate_percent}%)"


class Coupon(TenantOwnedModel):
    """
    A single, whole-cart discount code -- no per-product rules, no
    stacking (original spec: "تطبيق Coupon", singular). `times_used` is
    part of the schema now but deliberately NOT incremented by any
    apps.carts operation: incrementing it when a coupon is merely
    *applied to a cart* would let abandoned guest carts silently consume
    a merchant's limited-use coupon. It's meant to be incremented at
    actual order creation (Phase 8), which doesn't exist yet.
    """

    class Kind(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED_AMOUNT = "fixed_amount", "Fixed amount"

    code = models.CharField(max_length=64)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    percentage_value = models.PositiveIntegerField(null=True, blank=True)
    fixed_amount_value = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "pricing_coupon"
        constraints = [
            models.UniqueConstraint(fields=["store", "code"], name="uniq_coupon_code_per_store"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind="percentage",
                        percentage_value__isnull=False,
                        fixed_amount_value__isnull=True,
                    )
                    | models.Q(
                        kind="fixed_amount",
                        fixed_amount_value__isnull=False,
                        percentage_value__isnull=True,
                    )
                ),
                name="coupon_value_matches_kind",
            ),
            models.CheckConstraint(
                condition=models.Q(percentage_value__isnull=True)
                | (models.Q(percentage_value__gte=1) & models.Q(percentage_value__lte=100)),
                name="coupon_percentage_value_in_range",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.code
