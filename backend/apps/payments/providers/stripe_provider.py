"""
Real Stripe integration via the official `stripe` SDK (docs/ARCHITECTURE.md
section 8.1, roadmap Phase 9 DoD). This is production code, not a stub --
but see docs/PHASE_9_REPORT.md: there are no live Stripe test credentials
in this environment, so nothing here is exercised against Stripe's real
API in this session's test suite. Tests mock the SDK call boundary
(`stripe.PaymentIntent.create` etc.) and feed `verify_webhook` official,
documented Stripe webhook payload shapes as fixtures -- exactly what
docs/ARCHITECTURE.md section 14's testing strategy specifies ("mock
provider + أحداث مسجّلة"), applied to the real provider class too.

Never sets the process-global `stripe.api_key` -- this project is
multi-tenant and each store has its OWN Stripe secret key
(`StoreProviderConfig.credentials_encrypted`); a global would let one
store's decrypted key leak into a concurrent request for a different
store. Every SDK call passes `api_key=` explicitly instead.
"""

from __future__ import annotations

import stripe

from apps.payments.providers.base import (
    DomainPaymentEvent,
    PaymentContext,
    PaymentInitResult,
    PaymentProvider,
    ProviderCapabilities,
    SignatureVerificationError,
    TransactionResult,
    VerifiedWebhookEvent,
)

_SUCCEEDED_TYPES = {"payment_intent.succeeded"}
_FAILED_TYPES = {"payment_intent.payment_failed", "payment_intent.canceled"}


def _redact(stripe_object) -> dict:
    """Keeps only fields safe to persist -- never the full raw Stripe object
    (which can carry customer PII/payment-method details)."""
    return {
        "id": stripe_object.get("id"),
        "status": stripe_object.get("status"),
        "amount": stripe_object.get("amount"),
        "currency": stripe_object.get("currency"),
    }


class StripeProvider(PaymentProvider):
    provider_key = "stripe"

    def __init__(self, *, secret_key: str) -> None:
        self._secret_key = secret_key

    def create_payment(self, ctx: PaymentContext) -> PaymentInitResult:
        intent = stripe.PaymentIntent.create(
            amount=ctx.amount,
            currency=ctx.currency.lower(),
            metadata=ctx.metadata,
            api_key=self._secret_key,
            idempotency_key=ctx.provider_idempotency_key,
        )
        state = "succeeded" if intent.status == "succeeded" else "processing"
        return PaymentInitResult(
            provider_ref=intent.id,
            state=state,
            client_action={"client_secret": intent.client_secret},
        )

    def capture(self, *, provider_ref: str) -> TransactionResult:
        intent = stripe.PaymentIntent.capture(provider_ref, api_key=self._secret_key)
        outcome = "succeeded" if intent.status == "succeeded" else "failed"
        return TransactionResult(
            outcome=outcome,
            provider_ref=intent.id,
            amount=intent.amount,
            raw_response_redacted=_redact(intent),
        )

    def refund(self, *, provider_ref: str, amount: int) -> TransactionResult:
        refund = stripe.Refund.create(
            payment_intent=provider_ref, amount=amount, api_key=self._secret_key
        )
        outcome = "succeeded" if refund.status in ("succeeded", "pending") else "failed"
        return TransactionResult(
            outcome=outcome,
            provider_ref=refund.id,
            amount=amount,
            raw_response_redacted=_redact(refund),
        )

    def check_status(self, *, provider_ref: str) -> TransactionResult:
        intent = stripe.PaymentIntent.retrieve(provider_ref, api_key=self._secret_key)
        outcome = "succeeded" if intent.status == "succeeded" else "failed"
        return TransactionResult(
            outcome=outcome,
            provider_ref=intent.id,
            amount=intent.amount,
            raw_response_redacted=_redact(intent),
            retryable=outcome == "failed",
        )

    def verify_webhook(
        self, *, raw_body: bytes, headers: dict, secret: str
    ) -> VerifiedWebhookEvent:
        sig_header = headers.get("Stripe-Signature", "")
        try:
            event = stripe.Webhook.construct_event(raw_body, sig_header, secret)
        except (stripe.SignatureVerificationError, ValueError):
            raise SignatureVerificationError(
                "Stripe webhook signature verification failed"
            ) from None
        return VerifiedWebhookEvent(external_id=event["id"], raw_payload=event)

    def map_event(self, event: VerifiedWebhookEvent) -> DomainPaymentEvent:
        payload = event.raw_payload
        event_type = payload["type"]
        intent = payload["data"]["object"]

        if event_type in _SUCCEEDED_TYPES:
            kind = "payment_succeeded"
        elif event_type in _FAILED_TYPES:
            kind = "payment_failed"
        else:
            kind = "unhandled"

        last_error = intent.get("last_payment_error") or {}
        return DomainPaymentEvent(
            external_id=event.external_id,
            provider_ref=intent["id"],
            kind=kind,
            amount=intent["amount"],
            currency=intent["currency"].upper(),
            failure_reason=last_error.get("message", ""),
            # Stripe's `last_payment_error.code` covers both retryable (e.g.
            # `card_declined`) and terminal (e.g. `expired_card` on a dead
            # card) cases the same way -- without a definitive Stripe-side
            # signal, default to retryable=True (fail open toward letting
            # the shopper try again, never toward silently cancelling their
            # Order on an ambiguous signal).
            retryable=True if kind == "payment_failed" else None,
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            auth_capture=True, partial_refund=True, hosted_page=True, requires_webhook=True
        )
