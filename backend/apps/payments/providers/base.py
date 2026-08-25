"""
`PaymentProvider` ABC (docs/ARCHITECTURE.md section 8.1) -- a uniform
interface with zero provider-specific logic leaking into
`apps.payments.services`. Adding a new provider is one new file + one
registry entry, same principle as `apps.shipping.carriers.CarrierProvider`
(Phase 7).

All dataclasses here are the ONLY shape `apps.payments.services` ever
touches -- provider-specific SDK objects (a `stripe.PaymentIntent`, a raw
webhook dict) never escape a provider module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PaymentContext:
    order_id: str
    amount: int
    currency: str
    # Derived from the CLIENT's own Idempotency-Key (never a freshly-
    # generated value), so a retried `create_payment` call -- whether from
    # a genuine client retry or our own crash-recovery -- reaches the
    # provider with the SAME key every time. This is what closes the
    # dual-write gap: even if our app-level idempotency layer mistakenly
    # calls the provider twice for "the same" logical operation, the
    # provider's OWN idempotency guarantee de-dupes it (approved Phase 9
    # decision on external provider calls).
    provider_idempotency_key: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentInitResult:
    provider_ref: str
    state: str  # "processing" | "succeeded" | "failed" -- a PaymentIntent.State value
    client_action: dict | None = None  # e.g. {"redirect_url": ...}/{"client_secret": ...}; opaque
    failure_reason: str = ""
    retryable: bool | None = None


@dataclass(frozen=True, slots=True)
class TransactionResult:
    outcome: str  # "succeeded" | "failed" -- a PaymentTransaction.Outcome value
    provider_ref: str
    amount: int
    raw_response_redacted: dict = field(default_factory=dict)
    failure_reason: str = ""
    retryable: bool | None = None


@dataclass(frozen=True, slots=True)
class VerifiedWebhookEvent:
    """The output of `verify_webhook` -- by construction, only ever produced AFTER
    signature verification has already succeeded. `raw_payload` is provider-shaped;
    only `map_event` is allowed to interpret it."""

    external_id: str
    raw_payload: dict


@dataclass(frozen=True, slots=True)
class DomainPaymentEvent:
    """Provider-agnostic normalization of a verified webhook event -- the ONLY
    shape `apps.payments.services` webhook processing ever consumes."""

    external_id: str
    provider_ref: str
    kind: str  # "payment_succeeded" | "payment_failed"
    amount: int
    currency: str
    failure_reason: str = ""
    retryable: bool | None = None


class SignatureVerificationError(Exception):
    """Raised by `verify_webhook` -- the message must never include the secret,
    the raw body, or any part of the computed/expected signature."""


class ProviderCapabilities:
    __slots__ = (
        "auth_capture",
        "partial_refund",
        "hosted_page",
        "requires_webhook",
        "confirms_order_on_acceptance",
    )

    def __init__(
        self,
        *,
        auth_capture: bool = False,
        partial_refund: bool = False,
        hosted_page: bool = False,
        requires_webhook: bool = True,
        confirms_order_on_acceptance: bool = False,
    ) -> None:
        self.auth_capture = auth_capture
        self.partial_refund = partial_refund
        self.hosted_page = hosted_page
        self.requires_webhook = requires_webhook
        # True only for providers where *accepting* the method (create_payment
        # returning `processing`, not yet `succeeded`) is itself the business
        # commitment to fulfill -- COD's defining trait (approved Phase 9
        # review-round decision). Money hasn't moved; the merchant has simply
        # committed to the sale. False for every provider where `processing`
        # means "still waiting to find out if this will even succeed" (Stripe).
        self.confirms_order_on_acceptance = confirms_order_on_acceptance


class PaymentProvider(ABC):
    provider_key: str

    @abstractmethod
    def create_payment(self, ctx: PaymentContext) -> PaymentInitResult: ...

    @abstractmethod
    def capture(self, *, provider_ref: str) -> TransactionResult: ...

    @abstractmethod
    def refund(self, *, provider_ref: str, amount: int) -> TransactionResult: ...

    @abstractmethod
    def check_status(self, *, provider_ref: str) -> TransactionResult:
        """Authoritative, read-only status query -- used by the reconciliation worker
        (apps/payments/tasks.py) to resolve a `PaymentIntent` stuck in `processing`,
        via the SAME transition-application service webhook processing uses (never a
        second copy of the transition logic)."""

    @abstractmethod
    def verify_webhook(
        self, *, raw_body: bytes, headers: dict, secret: str
    ) -> VerifiedWebhookEvent: ...

    @abstractmethod
    def map_event(self, event: VerifiedWebhookEvent) -> DomainPaymentEvent: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...
