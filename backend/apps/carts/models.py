"""
Guest-first cart -- approved Phase 6 decision (full record in
docs/PHASE_6_REPORT.md): no `apps.customers` app, no customer
authentication, exists yet. A cart is identified purely by an opaque,
unguessable, hashed token -- never a JWT, never derivable from
`cart.id`/`store_id`, and never treated as an authentication credential
for anything beyond "which cart".

`CartItem.unit_price_amount`/`currency` are a SNAPSHOT taken when the
item is added (or last repriced) -- not a live join to
`ProductVariant.price_amount`. This is deliberate: a cart shouldn't
silently reprice itself just because a merchant edited a price while a
shopper had items sitting in their cart. `apps.carts.services.reprice_cart`
is the explicit, callable operation that refreshes snapshots from the
current catalog state -- the "إعادة تسعير كاملة على الخادم" the Phase 6
roadmap DoD calls for.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantOwnedModel


class Cart(TenantOwnedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ABANDONED = "abandoned", "Abandoned"

    # SHA-256 hex of a `secrets.token_urlsafe(32)` value (apps.core.tokens)
    # -- the raw token is handed to the client (HttpOnly cookie) and NEVER
    # stored. See apps/carts/services.py:get_or_create_cart.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    currency = models.CharField(max_length=3)

    coupon = models.ForeignKey(
        "pricing.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Totals are a snapshot maintained by apps/carts/services.py, not
    # computed on every read -- see this module's docstring.
    subtotal_amount = models.PositiveIntegerField(default=0)
    discount_amount = models.PositiveIntegerField(default=0)
    tax_amount = models.PositiveIntegerField(default=0)
    total_amount = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "carts_cart"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Cart {self.id} ({self.status})"


class CartItem(TenantOwnedModel):
    cart = models.ForeignKey("carts.Cart", on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="+"
    )
    quantity = models.PositiveIntegerField()
    # Snapshot at add/reprice time -- see this module's docstring.
    unit_price_amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)

    class Meta:
        db_table = "carts_cartitem"
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="uniq_one_line_per_variant"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="cartitem_quantity_positive"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.quantity} x {self.variant_id}"
