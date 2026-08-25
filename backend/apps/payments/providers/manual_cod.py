"""
Cash-on-delivery -- "أساسي للسوق الخليجي" (docs/ARCHITECTURE.md section
8.1). No external network call, no webhook (`requires_webhook=False`).

Two distinct business events, deliberately never conflated (Phase 9
review-round decision, docs/PHASE_9_REPORT.md):

* ACCEPTANCE: `create_payment` = "the shopper chose COD, the merchant is
  committing to fulfill this sale" -- immediate, `processing`.
  `capabilities.confirms_order_on_acceptance=True` tells
  `apps.payments.services.initiate_payment` to confirm the Order and
  commit inventory RIGHT HERE, at acceptance time -- not after delivery.
  No money has moved and no claim is made that it has.
* COLLECTION: `capture` = "the cash was actually collected on delivery"
  -- a distinct, explicitly merchant-triggered action (a dashboard
  endpoint), transitions the PaymentIntent to `succeeded`. Because the
  Order is already `confirmed` by this point,
  `apply_payment_transition`'s existing "only act if Order is still
  pending_payment" guard means this NEVER re-confirms the Order or
  re-fulfills inventory -- no new logic needed for that, it falls out of
  the guard that already existed for the concurrency invariants.
"""

from __future__ import annotations

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


class ManualCodProvider(PaymentProvider):
    provider_key = "manual_cod"

    def create_payment(self, ctx: PaymentContext) -> PaymentInitResult:
        provider_ref = f"cod_{ctx.provider_idempotency_key}"
        return PaymentInitResult(provider_ref=provider_ref, state="processing")

    def capture(self, *, provider_ref: str) -> TransactionResult:
        return TransactionResult(outcome="succeeded", provider_ref=provider_ref, amount=0)

    def refund(self, *, provider_ref: str, amount: int) -> TransactionResult:
        # Manual, off-system -- a real refund is a real-world cash handback the
        # merchant performs themselves; there is nothing for this provider to call.
        return TransactionResult(outcome="succeeded", provider_ref=provider_ref, amount=amount)

    def check_status(self, *, provider_ref: str) -> TransactionResult:
        raise NotImplementedError(
            "manual_cod has no external state to reconcile -- the reconciliation "
            "worker must filter these out via capabilities.requires_webhook."
        )

    def verify_webhook(
        self, *, raw_body: bytes, headers: dict, secret: str
    ) -> VerifiedWebhookEvent:
        raise SignatureVerificationError(
            "manual_cod has no webhooks -- this should never be called."
        )

    def map_event(self, event: VerifiedWebhookEvent) -> DomainPaymentEvent:
        raise NotImplementedError("manual_cod has no webhooks -- this should never be called.")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            auth_capture=True,
            partial_refund=False,
            hosted_page=False,
            requires_webhook=False,
            confirms_order_on_acceptance=True,
        )
