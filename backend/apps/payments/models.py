"""
Payments. Store-scoped only. Full scope record in docs/PHASE_9_REPORT.md
-- summary of the load-bearing decisions:

1. `apps.payments` depends on `apps.orders`, never the reverse (approved
   Phase 9 decision) -- an import-linter contract enforces this. Order
   FSM validity rules (`pending_payment -> confirmed/cancelled`) stay
   inside `apps.orders.services.confirm_order`/`cancel_order`; this app
   only decides WHEN to call them, never mutates `Order.status` directly.

2. `PaymentIntent.amount`/`currency` are a SNAPSHOT of `Order.total_amount`/
   `currency` at creation time -- same discipline as every snapshot in
   this project since Phase 8. Never re-read live from Order.

3. At most one non-terminal (`processing`) `PaymentIntent` per Order
   (partial unique constraint below) -- prevents duplicate active
   payment attempts from a retried initiation request. A NEW attempt is
   only possible once the previous one reached a terminal state
   (`succeeded`/`failed`/`cancelled`).

4. Payment FSM is explicit and NOT numeric-monotonic (approved Phase 9
   decision) -- see `apps/payments/services.py:_ALLOWED_TRANSITIONS`, a
   literal adjacency map, checked by membership, not by comparing state
   "ranks". Terminal states (`succeeded`, `failed`, `cancelled`) never
   transition again -- any further event for one is recorded as a
   `PaymentTransaction` (audit) but produces no state change and no
   side effect a second time. This is what makes payment-outcome
   application idempotent independent of `WebhookEvent` uniqueness
   (approved Phase 9 decision on the concurrency tests).

5. `retryable` on a `failed` `PaymentIntent` decides the Order-level
   consequence: a retryable failure leaves `Order.status` at
   `pending_payment` (the shopper can retry -- a new `PaymentIntent` may
   be created once this one is terminal); a non-retryable failure calls
   `apps.orders.services.cancel_order`.

6. `WebhookEvent` uniqueness is `(provider_config, external_id)`, NOT a
   bare global `external_id` -- an event id's namespace is scoped to
   the specific provider *account* (one `StoreProviderConfig`), not
   "ever seen anywhere across every store's Stripe account".

7. Credentials are envelope-encrypted (`apps/payments/encryption.py`,
   AES-256-GCM) -- `credentials_encrypted`/`webhook_secret_encrypted`
   are write-only from the API's perspective (see serializers.py);
   `credentials_hint` is the only plaintext-adjacent field ever
   returned, computed once at write time
   (`encryption.mask_secret`), never derived by decrypting on read.

8. COD ("قبول COD كوسيلة دفع" vs "تحصيل النقد فعليًا") -- REVISED in the
   Phase 9 review round after the initial implementation delayed Order
   confirmation until physical delivery, which was rejected. Current,
   approved semantics:
     * ACCEPTANCE (`create_payment` returns `processing`) confirms the
       Order and fulfills inventory IMMEDIATELY, at acceptance time --
       `ProviderCapabilities.confirms_order_on_acceptance=True` is what
       tells `initiate_payment` to do this (see
       apps/payments/providers/manual_cod.py's module docstring). No
       claim is made that money has moved.
     * COLLECTION (`ManualCodProvider.capture`, a distinct, later,
       explicitly merchant-triggered dashboard action) only transitions
       `PaymentIntent: processing -> succeeded`. It NEVER re-confirms
       the Order or re-fulfills inventory a second time --
       `apply_payment_transition`'s existing "only act if Order is
       still pending_payment" guard (point 4/5 above) already prevents
       that, since the Order left `pending_payment` at acceptance time.
   No speculative extra state (e.g. `confirmed_unpaid`) was added --
   "unpaid, awaiting collection" is fully represented by
   `PaymentIntent.state == processing` on an already-`confirmed` Order.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantOwnedModel


class StoreProviderConfig(TenantOwnedModel):
    class Mode(models.TextChoices):
        TEST = "test", "Test"
        LIVE = "live", "Live"

    provider_key = models.CharField(max_length=32)
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.TEST)
    is_enabled = models.BooleanField(default=True)

    # Write-only from the API's perspective -- see this module's docstring, point 7.
    credentials_encrypted = models.TextField(blank=True)
    credentials_hint = models.CharField(max_length=32, blank=True)
    webhook_secret_encrypted = models.TextField(blank=True)

    public_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_storeproviderconfig"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "provider_key"], name="uniq_provider_config_per_store"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.provider_key} ({self.mode}) for store {self.store_id}"


class PaymentIntent(TenantOwnedModel):
    class State(models.TextChoices):
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="payment_intents"
    )
    provider_config = models.ForeignKey(
        "payments.StoreProviderConfig", on_delete=models.PROTECT, related_name="payment_intents"
    )

    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PROCESSING)

    provider_ref = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=255)

    failure_reason = models.CharField(max_length=255, blank=True)
    retryable = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = "payments_paymentintent"
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(state="processing"),
                name="uniq_one_processing_payment_intent_per_order",
            ),
        ]
        indexes = [models.Index(fields=["store", "state", "updated_at"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"PaymentIntent {self.id} ({self.state}) for order {self.order_id}"


class PaymentTransaction(TenantOwnedModel):
    """Immutable audit ledger -- never updated or deleted, same convention as
    `apps.inventory.models.StockMovement`. One row per provider interaction, including
    ones that produced no local state change (e.g. an out-of-order or duplicate event)."""

    class Kind(models.TextChoices):
        AUTHORIZE = "authorize", "Authorize"
        CAPTURE = "capture", "Capture"
        REFUND = "refund", "Refund"
        VOID = "void", "Void"

    class Outcome(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    intent = models.ForeignKey(
        "payments.PaymentIntent", on_delete=models.CASCADE, related_name="transactions"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    amount = models.PositiveIntegerField()
    provider_ref = models.CharField(max_length=255, blank=True)
    # Provider payloads are redacted before storage (no card numbers, no full
    # secrets) -- same discipline as WebhookEvent.payload_redacted below.
    raw_response_redacted = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_paymenttransaction"
        indexes = [models.Index(fields=["store", "intent"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.kind}:{self.outcome} for intent {self.intent_id}"


class WebhookEvent(TenantOwnedModel):
    provider_config = models.ForeignKey(
        "payments.StoreProviderConfig", on_delete=models.PROTECT, related_name="webhook_events"
    )
    external_id = models.CharField(max_length=255)
    signature_valid = models.BooleanField()
    payload_redacted = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payments_webhookevent"
        constraints = [
            models.UniqueConstraint(
                fields=["provider_config", "external_id"], name="uniq_event_per_provider_config"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.external_id} ({'valid' if self.signature_valid else 'invalid'})"


class PaymentIdempotencyKey(TenantOwnedModel):
    """
    Payment-owned idempotency, deliberately NOT `apps.orders.IdempotencyKey`
    (approved Phase 9 decision: apps.payments must not depend long-term on
    an apps.orders implementation detail, and the fingerprint semantics
    genuinely differ here -- "which order + which provider", not "which
    checkout session"). Same DB-backed uniqueness + fingerprint shape and
    claim/replay algorithm as Phase 8's, applied to a different resource.
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
        db_table = "payments_paymentidempotencykey"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "key"], name="uniq_payment_idempotency_key_per_store"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.key} ({self.status})"
