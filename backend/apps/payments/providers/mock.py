"""
Deterministic mock provider -- the DoD-required "mock provider" for
Payments (docs/ARCHITECTURE.md section 8.1/14). Behaves like a REAL async
provider (Stripe-shaped): `create_payment` returns `processing`, and a
terminal outcome only arrives later via a webhook -- so tests exercising
this provider genuinely exercise the whole webhook pipeline, not a
shortcut around it.

Signature verification here is real HMAC-SHA256 (`hmac.compare_digest`,
constant-time) over a shared secret -- not a no-op -- so
`verify_webhook`'s wrong-signature/replay tests are proving real
verification logic, just against a fake provider instead of Stripe.
"""

from __future__ import annotations

import hashlib
import hmac
import json

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

_SIGNATURE_HEADER = "X-Mock-Signature"


def _sign(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


class MockProvider(PaymentProvider):
    provider_key = "mock"

    def create_payment(self, ctx: PaymentContext) -> PaymentInitResult:
        provider_ref = f"mock_pi_{ctx.provider_idempotency_key}"
        return PaymentInitResult(provider_ref=provider_ref, state="processing")

    def capture(self, *, provider_ref: str) -> TransactionResult:
        return TransactionResult(outcome="succeeded", provider_ref=provider_ref, amount=0)

    def refund(self, *, provider_ref: str, amount: int) -> TransactionResult:
        return TransactionResult(outcome="succeeded", provider_ref=provider_ref, amount=amount)

    def check_status(self, *, provider_ref: str) -> TransactionResult:
        """Deterministic default for the reconciliation worker's happy path (no
        persistent state of its own -- a test that needs a SPECIFIC reconciliation
        outcome constructs an ad-hoc `PaymentProvider` double instead of relying on
        this returning something configurable)."""
        return TransactionResult(
            outcome="failed", provider_ref=provider_ref, amount=0, retryable=False
        )

    def verify_webhook(
        self, *, raw_body: bytes, headers: dict, secret: str
    ) -> VerifiedWebhookEvent:
        provided = headers.get(_SIGNATURE_HEADER, "")
        expected = _sign(raw_body, secret)
        if not hmac.compare_digest(provided, expected):
            raise SignatureVerificationError("mock webhook signature mismatch")
        payload = json.loads(raw_body)
        return VerifiedWebhookEvent(external_id=payload["id"], raw_payload=payload)

    def map_event(self, event: VerifiedWebhookEvent) -> DomainPaymentEvent:
        payload = event.raw_payload
        data = payload["data"]
        kind = (
            "payment_succeeded"
            if payload["type"] == "payment_intent.succeeded"
            else "payment_failed"
        )
        return DomainPaymentEvent(
            external_id=event.external_id,
            provider_ref=data["provider_ref"],
            kind=kind,
            amount=data["amount"],
            currency=data["currency"],
            failure_reason=data.get("failure_reason", ""),
            retryable=data.get("retryable"),
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            auth_capture=True, partial_refund=True, hosted_page=False, requires_webhook=True
        )


def build_mock_signature_header(raw_body: bytes, secret: str) -> dict:
    """Test helper -- signs a payload exactly the way a real mock webhook sender would."""
    return {_SIGNATURE_HEADER: _sign(raw_body, secret)}
