"""Session-state edge cases not covered by the happy-path/revalidation test files --
each one exercises exactly one branch in apps/orders/services.py that a normal
happy-path flow never reaches."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.orders import services
from apps.orders.models import CheckoutSession, IdempotencyKey
from apps.orders.tests.conftest import (
    VALID_ADDRESS,
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
)

pytestmark = pytest.mark.django_db


def test_address_step_with_no_checkout_started_is_404(store_with_hostname, storefront_client):
    response = storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": "a@example.com", "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    assert response.status_code == 404


def test_shipping_step_with_no_checkout_started_is_404(store_with_hostname, storefront_client):
    response = storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": "01a028ed-0000-7000-8000-000000000000"},
        content_type="application/json",
    )
    assert response.status_code == 404


def test_shipping_step_before_address_is_rejected(variant_in_store, storefront_client):
    add_item_and_start_checkout(storefront_client, variant_in_store["variant_id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": "01a028ed-0000-7000-8000-000000000000"},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_address_step_on_an_expired_session_is_409(variant_in_store, storefront_client):
    ctx = variant_in_store
    session = add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    with store_db_context(ctx["store"]):
        CheckoutSession.objects.filter(id=session["id"]).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

    response = storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": "a@example.com", "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    assert response.status_code == 409


def test_shipping_step_on_an_expired_session_is_409(variant_in_store, storefront_client):
    ctx = variant_in_store
    session = add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": "a@example.com", "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    with store_db_context(ctx["store"]):
        CheckoutSession.objects.filter(id=session["id"]).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

    response = storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": "01a028ed-0000-7000-8000-000000000000"},
        content_type="application/json",
    )
    assert response.status_code == 409


def test_starting_checkout_twice_reuses_the_same_session(variant_in_store, storefront_client):
    ctx = variant_in_store
    first = add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    second = storefront_client.post("/api/v1/storefront/checkout/start")
    assert second.status_code == 201
    assert second.data["id"] == first["id"]


def test_shipping_step_not_completed_before_complete_is_400(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": "a@example.com", "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="edge-no-shipping",
    )
    assert response.status_code == 400


def test_cart_emptied_between_shipping_and_complete_is_400(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    cart = storefront_client.get("/api/v1/storefront/cart").data
    item_id = cart["items"][0]["id"]
    storefront_client.delete(f"/api/v1/storefront/cart/items/{item_id}")

    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="edge-empty-cart",
    )
    assert response.status_code == 400


def test_completing_twice_with_different_keys_after_success_is_404(
    variant_in_store, storefront_client
):
    """The session flips to `completed` inside the same transaction as the first
    successful Order -- a SECOND, different Idempotency-Key against that now-inactive
    session must not create a second Order."""
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    first = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="edge-key-a",
    )
    assert first.status_code == 201

    second = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="edge-key-b",
    )
    assert second.status_code == 404


def test_session_expired_only_at_complete_time_is_409(variant_in_store, storefront_client):
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    session = add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    with store_db_context(ctx["store"]):
        CheckoutSession.objects.filter(id=session["id"]).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="edge-expired-at-complete",
    )
    assert response.status_code == 409


def test_idempotency_key_stuck_pending_is_a_defensive_conflict(variant_in_store, storefront_client):
    """Defensive guard for a state normal Postgres MVCC never actually produces
    (apps/orders/services.py:checkout_complete's docstring) -- proven directly at the
    service layer since HTTP traffic alone cannot construct this state."""
    ctx = variant_in_store
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    session_data = add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])

    with store_db_context(ctx["store"]):
        session = CheckoutSession.objects.get(id=session_data["id"])
        fingerprint = services._fingerprint_for_session_id(session.id)
        IdempotencyKey.objects.create(
            store=ctx["store"],
            key="stuck-key",
            request_fingerprint=fingerprint,
            status=IdempotencyKey.Status.PENDING,
        )

    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="stuck-key",
    )
    assert response.status_code == 409
