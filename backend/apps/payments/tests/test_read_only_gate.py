"""
Phase 10 review-round required regression: a `read_only` Store must
reject NEW payment initiation (`POST storefront/payments/initiate`) --
the Phase 10 report proved dashboard writes and checkout/complete were
gated, but not this separate payment step, which can be reached for an
Order that was already created (and is still `pending_payment`) BEFORE
the Store became `read_only`.

Deliberately does NOT touch webhooks/reconciliation/COD-capture: those
complete or recover an ALREADY-STARTED PaymentIntent, not a new
purchase attempt, and must keep working regardless of `Store.status`
(see apps/payments/services.py's `initiate_payment` docstring).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.payments.tests.conftest import create_order, enable_provider, store_db_context

pytestmark = pytest.mark.django_db


def _mark_read_only(store) -> None:
    from apps.stores.models import Store

    with store_db_context(store):
        store.status = Store.Status.READ_ONLY
        store.save(update_fields=["status", "updated_at"])


def test_read_only_store_rejects_new_payment_initiation_with_no_side_effects(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    _mark_read_only(ctx["store"])

    with patch("apps.payments.providers.mock.MockProvider.create_payment") as mock_create_payment:
        response = storefront_client.post(
            "/api/v1/storefront/payments/initiate",
            {"order_id": order["id"], "provider_key": "mock"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="readonly-initiate-key",
        )

    assert response.status_code == 402, response.content
    mock_create_payment.assert_not_called()  # provider never reached

    from apps.orders.models import Order
    from apps.payments.models import PaymentIdempotencyKey, PaymentIntent

    with store_db_context(ctx["store"]):
        assert not PaymentIntent.objects.filter(order_id=order["id"]).exists()
        assert not PaymentIdempotencyKey.objects.filter(key="readonly-initiate-key").exists()
        assert Order.objects.get(id=order["id"]).status == Order.Status.PENDING_PAYMENT


def test_active_store_payment_initiation_is_unaffected(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="active-initiate-key",
    )
    assert response.status_code == 201, response.data


def test_read_only_store_does_not_block_webhook_processing_of_an_existing_intent(
    variant_in_store, storefront_client
):
    """The gate is scoped to NEW purchase attempts, never to completing an
    already-started one -- explicit non-goal from the review round."""
    import json

    from apps.payments.models import PaymentIntent
    from apps.payments.providers.mock import build_mock_signature_header

    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock", webhook_secret="wh-secret")
    order = create_order(ctx, storefront_client)

    initiate = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="pre-readonly-initiate-key",
    )
    assert initiate.status_code == 201, initiate.data
    intent_id = initiate.data["id"]

    with store_db_context(ctx["store"]):
        intent = PaymentIntent.objects.get(id=intent_id)
        provider_ref, amount, currency = intent.provider_ref, intent.amount, intent.currency

    _mark_read_only(ctx["store"])

    body = json.dumps(
        {
            "id": "evt_readonly_webhook",
            "type": "payment_intent.succeeded",
            "data": {"provider_ref": provider_ref, "amount": amount, "currency": currency},
        }
    ).encode()
    headers = build_mock_signature_header(body, "wh-secret")

    response = storefront_client.generic(
        "POST",
        f"/api/v1/webhooks/payments/mock/{ctx['store'].id}",
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    assert response.status_code == 200, response.content

    with store_db_context(ctx["store"]):
        assert PaymentIntent.objects.get(id=intent_id).state == "succeeded"
