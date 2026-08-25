"""
Pure provider unit tests -- no DB needed. Stripe tests mock the SDK call
boundary (`stripe.PaymentIntent.create` etc.) and construct real,
correctly-signed webhook payloads using Stripe's own documented signing
scheme -- exactly docs/ARCHITECTURE.md section 14's testing strategy
("mock provider + أحداث مسجّلة"), applied to the real `StripeProvider`
class too. No live network call to Stripe happens anywhere in this file
(approved Phase 9 decision: no live Stripe testing required)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
import stripe as stripe_sdk

from apps.payments.providers.base import (
    PaymentContext,
    SignatureVerificationError,
    VerifiedWebhookEvent,
)
from apps.payments.providers.manual_cod import ManualCodProvider
from apps.payments.providers.mock import MockProvider, build_mock_signature_header
from apps.payments.providers.stripe_provider import StripeProvider


def _ctx(
    *,
    order_id: str = "order-1",
    amount: int = 2000,
    currency: str = "SAR",
    provider_idempotency_key: str = "store-1:client-key-1",
    metadata: dict | None = None,
) -> PaymentContext:
    return PaymentContext(
        order_id=order_id,
        amount=amount,
        currency=currency,
        provider_idempotency_key=provider_idempotency_key,
        metadata=metadata if metadata is not None else {"order_number": "ORD-000001"},
    )


# -- MockProvider -----------------------------------------------------------------


def test_mock_create_payment_is_processing():
    result = MockProvider().create_payment(_ctx())
    assert result.state == "processing"
    assert result.provider_ref


def test_mock_create_payment_is_deterministic_for_the_same_idempotency_key():
    a = MockProvider().create_payment(_ctx())
    b = MockProvider().create_payment(_ctx())
    assert a.provider_ref == b.provider_ref


def test_mock_verify_webhook_accepts_a_correctly_signed_payload():
    body = json.dumps(
        {
            "id": "evt_1",
            "type": "payment_intent.succeeded",
            "data": {"provider_ref": "mock_pi_1", "amount": 2000, "currency": "SAR"},
        }
    ).encode()
    headers = build_mock_signature_header(body, "whsec_test")
    event = MockProvider().verify_webhook(raw_body=body, headers=headers, secret="whsec_test")
    assert event.external_id == "evt_1"


def test_mock_verify_webhook_rejects_wrong_signature():
    body = json.dumps({"id": "evt_1", "type": "payment_intent.succeeded", "data": {}}).encode()
    with pytest.raises(SignatureVerificationError):
        MockProvider().verify_webhook(
            raw_body=body, headers={"X-Mock-Signature": "deadbeef"}, secret="whsec_test"
        )


def test_mock_verify_webhook_rejects_signature_computed_with_a_different_secret():
    body = json.dumps({"id": "evt_1", "type": "payment_intent.succeeded", "data": {}}).encode()
    headers = build_mock_signature_header(body, "whsec_wrong")
    with pytest.raises(SignatureVerificationError):
        MockProvider().verify_webhook(raw_body=body, headers=headers, secret="whsec_test")


def test_mock_map_event_succeeded():
    payload = {
        "id": "evt_1",
        "type": "payment_intent.succeeded",
        "data": {"provider_ref": "mock_pi_1", "amount": 2000, "currency": "SAR"},
    }
    event = VerifiedWebhookEvent(external_id="evt_1", raw_payload=payload)
    domain_event = MockProvider().map_event(event)
    assert domain_event.kind == "payment_succeeded"
    assert domain_event.amount == 2000


def test_mock_map_event_failed_carries_retryable_flag():
    payload = {
        "id": "evt_2",
        "type": "payment_intent.payment_failed",
        "data": {
            "provider_ref": "mock_pi_1",
            "amount": 2000,
            "currency": "SAR",
            "failure_reason": "card_declined",
            "retryable": True,
        },
    }
    event = VerifiedWebhookEvent(external_id="evt_2", raw_payload=payload)
    domain_event = MockProvider().map_event(event)
    assert domain_event.kind == "payment_failed"
    assert domain_event.retryable is True
    assert domain_event.failure_reason == "card_declined"


def test_mock_capture():
    result = MockProvider().capture(provider_ref="mock_pi_1")
    assert result.outcome == "succeeded"


def test_mock_refund():
    result = MockProvider().refund(provider_ref="mock_pi_1", amount=500)
    assert result.outcome == "succeeded"
    assert result.amount == 500


def test_mock_capabilities_require_webhook():
    assert MockProvider().capabilities.requires_webhook is True


# -- ManualCodProvider --------------------------------------------------------------


def test_manual_cod_create_payment_is_processing():
    result = ManualCodProvider().create_payment(_ctx())
    assert result.state == "processing"


def test_manual_cod_capture_succeeds():
    result = ManualCodProvider().capture(provider_ref="cod_1")
    assert result.outcome == "succeeded"


def test_manual_cod_refund_is_a_no_op_marker_result():
    result = ManualCodProvider().refund(provider_ref="cod_1", amount=2000)
    assert result.outcome == "succeeded"
    assert result.amount == 2000


def test_manual_cod_does_not_require_a_webhook():
    assert ManualCodProvider().capabilities.requires_webhook is False


def test_manual_cod_confirms_order_on_acceptance():
    assert ManualCodProvider().capabilities.confirms_order_on_acceptance is True


def test_mock_and_stripe_do_not_confirm_order_on_acceptance():
    """Only a COD-shaped provider's `processing` is itself the business commitment
    -- Stripe/mock's `processing` means "still waiting to find out"."""
    assert MockProvider().capabilities.confirms_order_on_acceptance is False
    assert StripeProvider(secret_key="sk_test_x").capabilities.confirms_order_on_acceptance is False


def test_manual_cod_verify_webhook_always_raises():
    with pytest.raises(SignatureVerificationError):
        ManualCodProvider().verify_webhook(raw_body=b"{}", headers={}, secret="")


def test_manual_cod_check_status_always_raises():
    with pytest.raises(NotImplementedError):
        ManualCodProvider().check_status(provider_ref="cod_1")


def test_manual_cod_map_event_always_raises():
    from apps.payments.providers.base import VerifiedWebhookEvent

    with pytest.raises(NotImplementedError):
        ManualCodProvider().map_event(VerifiedWebhookEvent(external_id="x", raw_payload={}))


# -- StripeProvider (SDK boundary mocked, no live network call) --------------------


def test_stripe_create_payment_calls_the_sdk_with_the_derived_idempotency_key():
    fake_intent = MagicMock(
        id="pi_123", status="requires_payment_method", client_secret="secret_123"
    )
    with patch.object(stripe_sdk.PaymentIntent, "create", return_value=fake_intent) as mocked:
        result = StripeProvider(secret_key="sk_test_x").create_payment(_ctx())
    mocked.assert_called_once()
    assert mocked.call_args.kwargs["idempotency_key"] == "store-1:client-key-1"
    assert mocked.call_args.kwargs["api_key"] == "sk_test_x"
    assert result.state == "processing"
    assert result.provider_ref == "pi_123"


def test_stripe_never_sets_the_global_api_key():
    """Multi-tenant safety: each store has its own secret key -- a global
    `stripe.api_key` would let one store's key leak into another's request."""
    fake_intent = MagicMock(id="pi_123", status="processing", client_secret="secret_123")
    original_global_key = stripe_sdk.api_key
    with patch.object(stripe_sdk.PaymentIntent, "create", return_value=fake_intent):
        StripeProvider(secret_key="sk_test_x").create_payment(_ctx())
    assert stripe_sdk.api_key == original_global_key


def test_stripe_capture():
    fake_intent = MagicMock(id="pi_123", status="succeeded", amount=2000)
    with patch.object(stripe_sdk.PaymentIntent, "capture", return_value=fake_intent):
        result = StripeProvider(secret_key="sk_test_x").capture(provider_ref="pi_123")
    assert result.outcome == "succeeded"


def test_stripe_refund():
    fake_refund = MagicMock(id="re_123", status="succeeded")
    with patch.object(stripe_sdk.Refund, "create", return_value=fake_refund) as mocked:
        result = StripeProvider(secret_key="sk_test_x").refund(provider_ref="pi_123", amount=500)
    mocked.assert_called_once_with(payment_intent="pi_123", amount=500, api_key="sk_test_x")
    assert result.outcome == "succeeded"
    assert result.amount == 500


def test_stripe_check_status():
    fake_intent = MagicMock(id="pi_123", status="succeeded", amount=2000, currency="sar")
    with patch.object(stripe_sdk.PaymentIntent, "retrieve", return_value=fake_intent):
        result = StripeProvider(secret_key="sk_test_x").check_status(provider_ref="pi_123")
    assert result.outcome == "succeeded"
    assert result.retryable is False


def test_stripe_capabilities():
    caps = StripeProvider(secret_key="sk_test_x").capabilities
    assert caps.hosted_page is True
    assert caps.requires_webhook is True


def _sign_stripe_payload(payload: bytes, secret: str) -> str:
    """Constructs a header using Stripe's own documented v1 signing scheme."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_stripe_verify_webhook_accepts_a_correctly_signed_real_shaped_payload():
    payload = json.dumps(
        {
            "id": "evt_1RaCE",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 2000,
                    "currency": "sar",
                    "status": "succeeded",
                }
            },
        }
    ).encode()
    header = _sign_stripe_payload(payload, "whsec_test_secret")

    event = StripeProvider(secret_key="sk_test_x").verify_webhook(
        raw_body=payload, headers={"Stripe-Signature": header}, secret="whsec_test_secret"
    )
    assert event.external_id == "evt_1RaCE"


def test_stripe_verify_webhook_rejects_wrong_secret():
    payload = json.dumps({"id": "evt_1", "type": "payment_intent.succeeded", "data": {}}).encode()
    header = _sign_stripe_payload(payload, "whsec_wrong")
    with pytest.raises(SignatureVerificationError):
        StripeProvider(secret_key="sk_test_x").verify_webhook(
            raw_body=payload, headers={"Stripe-Signature": header}, secret="whsec_test_secret"
        )


def test_stripe_map_event_succeeded():
    payload = {
        "id": "evt_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_123", "amount": 2000, "currency": "sar"}},
    }
    event = VerifiedWebhookEvent(external_id="evt_1", raw_payload=payload)
    domain_event = StripeProvider(secret_key="sk_test_x").map_event(event)
    assert domain_event.kind == "payment_succeeded"
    assert domain_event.currency == "SAR"


def test_registry_returns_mock_and_manual_cod():
    from apps.payments.providers.registry import get_provider

    assert isinstance(get_provider(provider_key="mock"), MockProvider)
    assert isinstance(get_provider(provider_key="manual_cod"), ManualCodProvider)


def test_registry_returns_stripe_with_secret_key():
    from apps.payments.providers.registry import get_provider

    provider = get_provider(provider_key="stripe", secret_key="sk_test_x")
    assert isinstance(provider, StripeProvider)


def test_registry_stripe_without_secret_key_raises():
    from apps.payments.providers.registry import get_provider

    with pytest.raises(ValueError):
        get_provider(provider_key="stripe")


def test_registry_unknown_provider_key_raises():
    from apps.payments.providers.registry import get_provider

    with pytest.raises(ValueError):
        get_provider(provider_key="does_not_exist")


def test_stripe_map_event_unhandled_type_is_marked_unhandled():
    payload = {
        "id": "evt_3",
        "type": "payment_intent.created",  # a real Stripe event type we don't act on
        "data": {"object": {"id": "pi_123", "amount": 2000, "currency": "sar"}},
    }
    event = VerifiedWebhookEvent(external_id="evt_3", raw_payload=payload)
    domain_event = StripeProvider(secret_key="sk_test_x").map_event(event)
    assert domain_event.kind == "unhandled"


def test_stripe_map_event_failed_extracts_the_decline_reason():
    payload = {
        "id": "evt_2",
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": "pi_123",
                "amount": 2000,
                "currency": "sar",
                "last_payment_error": {
                    "code": "card_declined",
                    "message": "Your card was declined.",
                },
            }
        },
    }
    event = VerifiedWebhookEvent(external_id="evt_2", raw_payload=payload)
    domain_event = StripeProvider(secret_key="sk_test_x").map_event(event)
    assert domain_event.kind == "payment_failed"
    assert domain_event.failure_reason == "Your card was declined."
    assert domain_event.retryable is True
