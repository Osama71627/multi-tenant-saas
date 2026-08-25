"""
Shipping configuration. Store-scoped only (no ambiguity here -- every
merchant defines their own zones/methods/rates, same as every other
domain model in this project).

Scope decisions locked in for Phase 7 (full record in
docs/PHASE_7_REPORT.md):

1. `Shipment` (order fulfillment tracking) is explicitly NOT built here
   -- it belongs to a real `Order`, which doesn't exist until Phase 8.
   This app stops at "what are the valid shipping options and their
   prices for a destination", matching docs/ARCHITECTURE.md section 9's
   own model list split (Zone/Method/Rate here; Shipment is Phase 8's).

2. No `Cart.shipping_method` field, no persisted shipping selection.
   `apps.carts` calls this app's pure quote engine read-only. Per the
   user's explicit Phase 8 mandate: a cart-level snapshot must never
   become "the" authority Order creation trusts -- keeping shipping
   selection out of Cart's persisted state entirely avoids that
   temptation. Checkout (Phase 8) is where a shipping CHOICE gets made
   and authoritatively re-priced.

3. Destination is ad-hoc (country_code/region passed directly in a
   quote request), not owned by any stored model -- there is no
   Customer/Address yet (Phase 6's guest-first decision). Whichever
   phase adds real addresses can start passing a stored address's
   fields into the exact same quote functions unchanged.

4. Tax-on-shipping coupling is explicitly UNRESOLVED here, on purpose
   -- Phase 6's tax calculation only ever taxes `subtotal - discount`;
   shipping isn't part of any persisted total yet (see #2), so there is
   nothing to couple yet. This decision is deferred to Phase 8, where
   the Order model reconciles subtotal/discount/tax/shipping together
   for the first time.
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.tenancy.models import TenantOwnedModel


class ShippingZone(TenantOwnedModel):
    """
    A destination-matching group. `priority` (lower = matched first)
    resolves the case where a destination matches more than one zone
    (e.g. a catch-all zone with empty `countries` alongside a specific
    "GCC" zone) -- explicit and merchant-controllable, rather than an
    implicit "most specific wins" heuristic that would be harder to
    reason about or override.
    """

    name = models.CharField(max_length=255)
    countries = ArrayField(
        models.CharField(max_length=2),
        default=list,
        blank=True,
        help_text="ISO 3166-1 alpha-2 codes. Empty means 'matches any country' (a catch-all zone).",
    )
    regions = ArrayField(models.CharField(max_length=255), default=list, blank=True)
    postal_patterns = ArrayField(
        models.CharField(max_length=32),
        default=list,
        blank=True,
        help_text="Postal-code PREFIXES (e.g. '11' matches any code starting with '11').",
    )
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "shipping_shippingzone"
        ordering = ["priority", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

    def matches(self, *, country_code: str, region: str = "", postal_code: str = "") -> bool:
        if self.countries and country_code not in self.countries:
            return False
        if self.regions and region not in self.regions:
            return False
        if self.postal_patterns:
            if not postal_code or not any(postal_code.startswith(p) for p in self.postal_patterns):
                return False
        return True


class ShippingMethod(TenantOwnedModel):
    class Kind(models.TextChoices):
        FLAT = "flat", "Flat rate"
        FREE = "free", "Free shipping"
        WEIGHT_BASED = "weight_based", "Weight based"
        PRICE_BASED = "price_based", "Order value based"
        CARRIER_CALCULATED = "carrier_calculated", "Carrier calculated"

    zone = models.ForeignKey(
        "shipping.ShippingZone", on_delete=models.CASCADE, related_name="methods"
    )
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "shipping_shippingmethod"
        ordering = ["position", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class ShippingRate(TenantOwnedModel):
    """
    A pricing tier for a `weight_based`/`price_based` method (`min_value`/
    `max_value` bound a weight-in-grams or a subtotal-in-minor-units
    range depending on the method's kind), or the single unbounded row
    for a `flat`/`free` method. Never used for `carrier_calculated` --
    that kind's price comes from `apps.shipping.carriers` instead.
    """

    method = models.ForeignKey(
        "shipping.ShippingMethod", on_delete=models.CASCADE, related_name="rates"
    )
    min_value = models.PositiveIntegerField(null=True, blank=True)
    max_value = models.PositiveIntegerField(null=True, blank=True)
    price_amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)

    class Meta:
        db_table = "shipping_shippingrate"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_value__isnull=True)
                | models.Q(min_value__isnull=True)
                | models.Q(max_value__gte=models.F("min_value")),
                name="shippingrate_max_not_below_min",
            ),
        ]
        ordering = ["min_value"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.method_id}: {self.min_value}-{self.max_value} = {self.price_amount}"
