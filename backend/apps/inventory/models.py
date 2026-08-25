"""
Inventory. Architecture decisions locked in for Phase 5 (full record in
docs/PHASE_5_REPORT.md):

1. Multi-location from day one. `ProductVariant` (apps.catalog) carries
   ZERO stock fields -- it never did (Phase 4 decision) and never will.
   Stock is keyed to (store, location, variant) via `StockBalance`, not
   to the variant alone. No "Default Location" is auto-created anywhere
   (not in Catalog, not here) -- a merchant/service explicitly creates a
   `StockLocation` before any stock can exist for it.

2. Two clearly separated levels, per the approved design:
     * `StockBalance` -- the OPERATIONAL source of truth for "how much
       is there right now": stored `quantity_on_hand` / `quantity_reserved`
       counters per (variant, location), updated in place. `available`
       is ALWAYS derived (`on_hand - reserved`), never stored, so it can
       never drift out of sync with its own inputs.
     * `StockMovement` -- an immutable audit ledger. Every operation
       that changes a balance appends a row here (with a snapshot of the
       resulting balance for audit trails) but movements are never read
       to reconstruct current state -- `StockBalance` already IS that
       state. Movements are never updated or deleted by application
       code.
   `StockReservation` is a third, separate operational table (not
   derived from the ledger) so a specific reservation -- "give back
   exactly what THIS cart/session reserved" -- can be released by
   reference without re-deriving state from history.

3. Concurrency: every mutating operation (`services.py`) locks the
   `StockBalance` row with `select_for_update()` inside
   `transaction.atomic()` before reading/writing it -- this scopes
   contention to one (variant, location) pair, not the whole table.
   Backed by three DB-level `CHECK` constraints as the actual,
   can't-be-bypassed guarantee against overselling (verified with a
   real two-connection concurrency test, not app-level trust alone):
   `quantity_on_hand >= 0`, `quantity_reserved >= 0`, and
   `quantity_reserved <= quantity_on_hand`.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantOwnedModel


class StockLocation(TenantOwnedModel):
    """A warehouse / pickup point that can hold stock. Explicitly created, never implied."""

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_stocklocation"
        constraints = [
            models.UniqueConstraint(fields=["store", "name"], name="uniq_location_name_per_store"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class StockBalance(TenantOwnedModel):
    """
    Operational source of truth for current stock -- see this module's
    docstring. NOT append-only; `services.py` mutates these counters in
    place under a row lock.
    """

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="stock_balances"
    )
    location = models.ForeignKey(
        "inventory.StockLocation", on_delete=models.CASCADE, related_name="stock_balances"
    )
    quantity_on_hand = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "inventory_stockbalance"
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "location"], name="uniq_balance_per_variant_location"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_on_hand__gte=0),
                name="stockbalance_on_hand_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__gte=0),
                name="stockbalance_reserved_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__lte=models.F("quantity_on_hand")),
                name="stockbalance_reserved_not_exceeding_on_hand",
            ),
        ]

    @property
    def quantity_available(self) -> int:
        """Always derived, never stored -- see this module's docstring."""
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def is_low_stock(self) -> bool:
        if self.low_stock_threshold is None:
            return False
        return self.quantity_available <= self.low_stock_threshold

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.variant_id} @ {self.location_id}: {self.quantity_on_hand}"


class StockMovement(TenantOwnedModel):
    """
    Immutable audit ledger -- never the source of truth for current
    state, never updated or deleted. `balance_on_hand_after` /
    `balance_reserved_after` are point-in-time snapshots for audit
    reading, not live values.
    """

    class Kind(models.TextChoices):
        ADJUSTMENT = "adjustment", "Manual adjustment"
        RESERVE = "reserve", "Reserved"
        RELEASE = "release", "Reservation released"
        FULFILL = "fulfill", "Reservation fulfilled"

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="stock_movements"
    )
    location = models.ForeignKey(
        "inventory.StockLocation", on_delete=models.CASCADE, related_name="stock_movements"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    delta_on_hand = models.IntegerField(default=0)
    delta_reserved = models.IntegerField(default=0)
    balance_on_hand_after = models.IntegerField()
    balance_reserved_after = models.IntegerField()
    reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Caller-supplied correlation id (e.g. a future cart/order id), opaque here.",
    )
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "inventory_stockmovement"
        indexes = [
            models.Index(fields=["store", "variant", "location"]),
            models.Index(fields=["store", "reference"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.kind}: {self.variant_id} @ {self.location_id} ({self.delta_on_hand:+d})"


class StockReservation(TenantOwnedModel):
    """
    A specific, individually-releasable reservation -- deliberately NOT
    derived from `StockMovement` (see this module's docstring on why).
    `reference` is caller-supplied and opaque (no FK to Cart/Order --
    those don't exist yet, and Inventory must not depend on them).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RELEASED = "released", "Released"
        FULFILLED = "fulfilled", "Fulfilled"

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="reservations"
    )
    location = models.ForeignKey(
        "inventory.StockLocation", on_delete=models.CASCADE, related_name="reservations"
    )
    quantity = models.PositiveIntegerField()
    reference = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory_stockreservation"
        indexes = [
            models.Index(fields=["store", "reference"]),
            models.Index(fields=["store", "status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.reference}: {self.quantity} of {self.variant_id} ({self.status})"
