"""Real HTTP webhook processing (docs/ARCHITECTURE.md section 8.4). MockProvider's
real HMAC signature verification -- not a shortcut -- proves the whole pipeline
(signature check -> claim -> correlate -> verify amount/currency -> apply transition)."""

from __future__ import annotations

import json

import pytest

from apps.payments.providers.mock import build_mock_signature_header
from apps.payments.tests.conftest import create_order, enable_provider, store_db_context

pytestmark = pytest.mark.django_db


def _initiate(ctx, storefront_client, order, *, key="webhook-init-key") -> dict:
    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data


def _webhook_url(ctx, provider="mock"):
    return f"/api/v1/webhooks/payments/{provider}/{ctx['store'].id}"


def _success_body(intent_id: str, *, amount: int, currency: str = "SAR") -> bytes:
    return json.dumps(
        {
            "id": f"evt_{intent_id}",
            "type": "payment_intent.succeeded",
            "data": {"provider_ref": intent_id, "amount": amount, "currency": currency},
        }
    ).encode()


def test_valid_success_webhook_confirms_the_order(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock", webhook_secret="whsec_test")
    order = create_order(ctx, storefront_client)
    intent_data = _initiate(ctx, storefront_client, order)

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentIntent

        intent = PaymentIntent.objects.get(id=intent_data["id"])
        provider_ref = intent.provider_ref
        amount = intent.amount

    body = _success_body(provider_ref, amount=amount)
    headers = build_mock_signature_header(body, "whsec_test")

    response = storefront_client.generic(
        "POST",
        _webhook_url(ctx),
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    assert response.status_code == 200, response.content

    with store_db_context(ctx["store"]):
        from apps.orders.models import Order

        assert Order.objects.get(id=order["id"]).status == Order.Status.CONFIRMED


def test_invalid_signature_is_rejected_with_no_side_effect(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock", webhook_secret="whsec_test")
    order = create_order(ctx, storefront_client)
    intent_data = _initiate(ctx, storefront_client, order)

    body = _success_body(intent_data["id"], amount=2000)
    response = storefront_client.generic(
        "POST",
        _webhook_url(ctx),
        data=body,
        content_type="application/json",
        HTTP_X_MOCK_SIGNATURE="wrong-signature",
    )
    assert response.status_code == 400

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentIntent

        assert PaymentIntent.objects.get(id=intent_data["id"]).state == "processing"


def test_duplicate_delivery_is_not_reprocessed(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock", webhook_secret="whsec_test")
    order = create_order(ctx, storefront_client)
    intent_data = _initiate(ctx, storefront_client, order)

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentIntent

        intent = PaymentIntent.objects.get(id=intent_data["id"])
        provider_ref, amount = intent.provider_ref, intent.amount

    body = _success_body(provider_ref, amount=amount)
    headers = build_mock_signature_header(body, "whsec_test")
    http_headers = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()}

    first = storefront_client.generic(
        "POST", _webhook_url(ctx), data=body, content_type="application/json", **http_headers
    )
    second = storefront_client.generic(
        "POST", _webhook_url(ctx), data=body, content_type="application/json", **http_headers
    )
    assert first.status_code == 200
    assert second.status_code == 200

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentTransaction, WebhookEvent

        events = WebhookEvent.objects.filter(external_id=f"evt_{provider_ref}")
        assert events.count() == 1
        assert events.first().attempts == 2
        # Only ONE PaymentTransaction (succeeded) was ever recorded for this intent.
        assert PaymentTransaction.objects.filter(intent_id=intent_data["id"]).count() == 1


def test_amount_mismatch_is_not_applied(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock", webhook_secret="whsec_test")
    order = create_order(ctx, storefront_client)
    intent_data = _initiate(ctx, storefront_client, order)

    with store_db_context(ctx["store"]):
        from apps.payments.models import PaymentIntent

        provider_ref = PaymentIntent.objects.get(id=intent_data["id"]).provider_ref

    body = _success_body(provider_ref, amount=999999)  # does not match the intent's real amount
    headers = build_mock_signature_header(body, "whsec_test")
    response = storefront_client.generic(
        "POST",
        _webhook_url(ctx),
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    assert response.status_code == 200  # acknowledged, but NOT applied

    with store_db_context(ctx["store"]):
        from apps.orders.models import Order

        assert Order.objects.get(id=order["id"]).status == Order.Status.PENDING_PAYMENT


def test_webhook_for_an_unresolvable_store_id_is_404():
    import uuid

    from django.test import Client

    response = Client().post(
        f"/api/v1/webhooks/payments/mock/{uuid.uuid4()}",
        data=b"{}",
        content_type="application/json",
    )
    assert response.status_code == 404


def test_webhook_for_an_unconfigured_provider_is_404(store_with_hostname, storefront_client):
    ctx = store_with_hostname
    response = storefront_client.generic(
        "POST", _webhook_url(ctx), data=b"{}", content_type="application/json"
    )
    assert response.status_code == 404


def test_unknown_provider_ref_does_not_error(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock", webhook_secret="whsec_test")
    body = _success_body("mock_pi_does_not_exist", amount=2000)
    headers = build_mock_signature_header(body, "whsec_test")
    response = storefront_client.generic(
        "POST",
        _webhook_url(ctx),
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    assert response.status_code == 200
