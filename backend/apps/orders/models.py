"""
Checkout & Orders. Store-scoped only. Full scope record in
docs/PHASE_8_REPORT.md -- summary of the load-bearing decisions:

1. Guest checkout only (approved Phase 8 architecture decision 1): no
   `apps.customers`, no customer FK. `Order.email` is the only required
   identity. A nullable `customer_id` can be added by a later, additive
   migration once a Customer bounded context exists -- it does not
   exist yet, so it is not pre-built here.

2. `Order`/`OrderItem` are IMMUTABLE FINANCIAL SNAPSHOTS. After an Order
   is created, nothing about its money depends on live
   `ProductVariant`/`TaxRate`/`Coupon`/`ShippingRate` state ever again.
   `OrderItem.variant` is a nullable (`SET_NULL`) REFERENCE only -- never
   the source of truth for price/name/sku, which are copied at checkout
   time. This mirrors `CartItem`'s existing snapshot discipline (Phase 6)
   and extends it, rather than replacing it with something new.

3. Totals semantics (mirrors `apps.pricing.calculator.calculate_totals`,
   extended with shipping -- see `apps/orders/services.py`):
       subtotal_amount  = sum(item.unit_price_amount * item.quantity)
       discount_amount  = calculate_discount(subtotal_amount, coupon)   -- never > subtotal
       tax_amount       = calculate_tax(subtotal_amount - discount_amount, tax_rate)
       shipping_amount  = authoritative shipping quote at commit time, NOT taxed
                           (approved Phase 8 decision 11: shipping excluded from tax base)
       total_amount     = (subtotal_amount - discount_amount) + tax_amount + shipping_amount
   `apps.pricing.calculator` is reused UNMODIFIED for the first four --
   shipping is composed on top in `apps.orders.services`, not folded
   into a fourth pricing engine.

4. `billing_address` is deliberately NOT a field here -- Phase 8 has no
   requirement that depends on it (no payment capture, no invoicing
   distinct from the shipping destination), and the original v1 sketch
   in docs/ARCHITECTURE.md section 4.2 lists it speculatively alongside
   `shipping_address`. Adding it is an additive, non-breaking migration
   whenever a real requirement appears.

5. No `Shipment`/`Fulfillment` tables (approved Phase 8 decision 13) --
   `Order.fulfillment_status` is a single field, not a table, exactly
   because Phase 8's DoD ends at Order creation.

6. `Order.status` carries exactly one value in Phase 8:
   `pending_payment`. No `confirmed`/`cancelled`/etc. yet -- nothing in
   this phase transitions an Order out of `pending_payment` (approved
   Phase 8 decision 12: no COD semantics here, Phase 9's job). Extending
   `TextChoices` later is an additive, non-breaking migration.

7. `StockReservation.reference` contract: `f"order:{order.id}"` --
   formalizing the opaque-correlation-identifier contract that
   `apps.inventory.models.StockReservation`'s docstring already
   anticipated ("no FK to Cart/Order -- those don't exist yet, and
   Inventory must not depend on them", Phase 5). A real FK from
   `StockReservation` to `Order` would force `apps.inventory` to import
   `apps.orders`, inverting the layering direction enforced by every
   import-linter contract so far (lower layers never import higher
   ones) -- exactly the reason that field was designed as an opaque
   string in the first place, not a gap being patched around now.
   `StockReservation.Meta.indexes` already covers `(store, reference)`,
   so the recurring "find this order's reservations" lookup this
   contract implies is indexed, not a table scan.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantOwnedModel


def order_reservation_reference(order_id) -> str:
    """The one place that formats/parses the `StockReservation.reference` contract for
    Orders (see this module's docstring, point 7). Never build this string inline elsewhere."""
    return f"order:{order_id}"


class CheckoutSession(TenantOwnedModel):
    """
    Transient state for the `checkout/start -> address -> shipping ->
    complete` sequence (docs/ARCHITECTURE.md section 5.3 -- `payment` is
    out of scope for Phase 8, see apps/orders/views.py's module
    docstring). Everything here is INTENT, never authority: `complete`
    re-derives and re-validates everything from scratch (approved Phase
    8 decisions 4 and 9) rather than trusting what's stored here.

    One `Cart` may have at most one ACTIVE `CheckoutSession` at a time
    (partial unique constraint below) -- `checkout/start` reuses an
    existing active, unexpired one instead of creating a duplicate.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    cart = models.ForeignKey(
        "carts.Cart", on_delete=models.CASCADE, related_name="checkout_sessions"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()

    email = models.EmailField(blank=True)
    shipping_address = models.JSONField(null=True, blank=True)

    # Shipping INTENT only -- captured for display/continuity between
    # steps. `SET_NULL` because a merchant can delete/disable a
    # ShippingMethod out from under an in-progress checkout; `complete`
    # never trusts these snapshot fields as authoritative (decision 4).
    shipping_method = models.ForeignKey(
        "shipping.ShippingMethod",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    shipping_method_name_snapshot = models.CharField(max_length=255, blank=True)
    shipping_amount_snapshot = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "orders_checkoutsession"
        constraints = [
            models.UniqueConstraint(
                fields=["cart"],
                condition=models.Q(status="active"),
                name="uniq_one_active_checkout_session_per_cart",
            ),
        ]
        indexes = [models.Index(fields=["store", "expires_at"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"CheckoutSession {self.id} ({self.status})"


class OrderNumberSequence(TenantOwnedModel):
    """
    One row per store, locked with `select_for_update()` inside the same
    atomic transaction as Order creation (apps/orders/services.py) --
    same discipline as `StockBalance` row-locking in apps.inventory
    (Phase 5). A dedicated table here, not a counter field bolted onto
    `Store`, keeps this entirely inside apps.orders: apps.stores must
    not gain an orders-shaped concern just to support numbering.
    """

    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "orders_ordernumbersequence"
        constraints = [
            models.UniqueConstraint(fields=["store"], name="uniq_one_sequence_per_store"),
        ]


class Order(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        # Added additively in Phase 9 (apps.payments) -- exactly the
        # non-breaking migration this module's docstring (point 6)
        # anticipated. `apps.orders.services.confirm_order`/`cancel_order`
        # are the only sanctioned way to reach these states -- both lock
        # the row and require the CURRENT status to be `pending_payment`,
        # keeping the Order FSM's own validity rules inside apps.orders
        # even though apps.payments is what decides WHEN to call them
        # (Order FSM and Payment FSM stay deliberately separate --
        # docs/PHASE_9_REPORT.md).

    class FulfillmentStatus(models.TextChoices):
        UNFULFILLED = "unfulfilled", "Unfulfilled"

    number = models.CharField(max_length=32, db_index=True)
    email = models.EmailField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_PAYMENT)
    fulfillment_status = models.CharField(
        max_length=24, choices=FulfillmentStatus.choices, default=FulfillmentStatus.UNFULFILLED
    )
    currency = models.CharField(max_length=3)

    subtotal_amount = models.PositiveIntegerField()
    discount_amount = models.PositiveIntegerField()
    tax_amount = models.PositiveIntegerField()
    shipping_amount = models.PositiveIntegerField()
    total_amount = models.PositiveIntegerField()

    shipping_address = models.JSONField()
    shipping_method_name_snapshot = models.CharField(max_length=255)

    coupon_code_snapshot = models.CharField(max_length=64, blank=True)

    # No separate `placed_at` -- Phase 8 has no draft-order concept, an
    # Order is placed at the exact moment it's created, so the inherited
    # `created_at` (TimeStampedModel) already carries that meaning; a
    # second identical timestamp field would be redundant state.

    class Meta:
        db_table = "orders_order"
        constraints = [
            models.UniqueConstraint(fields=["store", "number"], name="uniq_order_number_per_store"),
        ]
        indexes = [models.Index(fields=["store", "status", "created_at"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Order {self.number}"


class OrderItem(TenantOwnedModel):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    variant_name_snapshot = models.CharField(max_length=255)
    variant_sku_snapshot = models.CharField(max_length=64)
    variant_options_snapshot = models.JSONField(default=list, blank=True)

    unit_price_amount = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)

    class Meta:
        db_table = "orders_orderitem"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="orderitem_quantity_positive"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.quantity} x {self.variant_sku_snapshot}"

    @property
    def line_total_amount(self) -> int:
        """Derived, never stored -- `unit_price_amount` is already an immutable
        snapshot, so this is deterministic and storing it would be redundant state."""
        return self.unit_price_amount * self.quantity


class IdempotencyKey(TenantOwnedModel):
    """
    DB-backed correctness boundary for `POST checkout/complete`
    (docs/ARCHITECTURE.md section 5.2 mandates the `Idempotency-Key`
    header). Redis MAY sit in front of this as a fast-path cache, but
    this table is the actual invariant: `(store, key)` uniqueness is
    what makes two concurrent requests with the same key resolve to
    exactly one Order, via Postgres's unique-index insert blocking (see
    apps/orders/services.py:checkout_complete for the full mechanism).

    `request_fingerprint` catches "same key, different payload": a
    replay must match it exactly, or the request is rejected with a
    conflict rather than silently replaying an unrelated response.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    key = models.CharField(max_length=255)
    request_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "orders_idempotencykey"
        constraints = [
            models.UniqueConstraint(fields=["store", "key"], name="uniq_idempotency_key_per_store"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.key} ({self.status})"
