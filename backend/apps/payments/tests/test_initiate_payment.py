from __future__ import annotations

import pytest

from apps.payments.tests.conftest import create_order, enable_provider

pytestmark = pytest.mark.django_db


def test_initiate_payment_with_mock_provider(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-1",
    )
    assert response.status_code == 201, response.data
    assert response.data["state"] == "processing"
    assert response.data["order_id"] == order["id"]


def test_initiate_payment_with_manual_cod(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "manual_cod"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-cod",
    )
    assert response.status_code == 201, response.data
    assert response.data["provider_key"] == "manual_cod"


def test_initiate_payment_requires_idempotency_key(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_initiate_payment_for_unconfigured_provider_is_400(variant_in_store, storefront_client):
    ctx = variant_in_store
    order = create_order(ctx, storefront_client)

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-unconfigured",
    )
    assert response.status_code == 400


def test_repeating_the_same_idempotency_key_replays(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    first = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-repeat",
    )
    second = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-repeat",
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["id"] == second.data["id"]

    from apps.payments.models import PaymentIntent
    from apps.payments.tests.conftest import store_db_context

    with store_db_context(ctx["store"]):
        assert PaymentIntent.objects.filter(order_id=order["id"]).count() == 1


def test_cannot_start_a_second_active_payment_for_the_same_order(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    first = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-dup-a",
    )
    assert first.status_code == 201

    second = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-dup-b",
    )
    assert second.status_code == 409


def test_cannot_initiate_payment_for_an_order_that_is_not_pending(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    from apps.orders.models import Order
    from apps.payments.tests.conftest import store_db_context

    with store_db_context(ctx["store"]):
        Order.objects.filter(id=order["id"]).update(status=Order.Status.CANCELLED)

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-cancelled-order",
    )
    assert response.status_code == 409


def test_reusing_the_same_key_for_a_different_order_is_a_conflict(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order_a = create_order(ctx, storefront_client, quantity=1)
    order_b = create_order(ctx, storefront_client, quantity=2)

    first = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order_a["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="shared-init-key",
    )
    assert first.status_code == 201

    second = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order_b["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="shared-init-key",
    )
    assert second.status_code == 409


def test_an_idempotency_key_still_pending_is_a_conflict(variant_in_store, storefront_client):
    """A genuinely reachable state here (unlike apps.orders.checkout_complete) since
    `initiate_payment` has a real network-call gap between claiming the key and
    completing it -- see apps/payments/services.py's module docstring."""
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    from apps.payments.models import PaymentIdempotencyKey
    from apps.payments.services import _fingerprint
    from apps.payments.tests.conftest import store_db_context

    with store_db_context(ctx["store"]):
        PaymentIdempotencyKey.objects.create(
            store=ctx["store"],
            key="stuck-init-key",
            request_fingerprint=_fingerprint(order["id"], "mock"),
            status=PaymentIdempotencyKey.Status.PENDING,
        )

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="stuck-init-key",
    )
    assert response.status_code == 409


def test_get_provider_for_config_decrypts_stripe_credentials(variant_in_store):
    from apps.payments import encryption, services
    from apps.payments.models import StoreProviderConfig
    from apps.payments.providers.stripe_provider import StripeProvider
    from apps.payments.tests.conftest import store_db_context

    ctx = variant_in_store
    with store_db_context(ctx["store"]):
        config = StoreProviderConfig.objects.create(
            store=ctx["store"],
            provider_key="stripe",
            credentials_encrypted=encryption.encrypt_secret("sk_test_real_key"),
        )
        provider = services.get_provider_for_config(config)
        assert isinstance(provider, StripeProvider)
        assert provider._secret_key == "sk_test_real_key"  # noqa: S105


def test_synchronous_success_at_initiation_confirms_the_order_immediately(
    variant_in_store, storefront_client, monkeypatch
):
    """Defensive path for a hypothetical instant-settlement provider -- none of
    mock/manual_cod/stripe resolve synchronously today, but `initiate_payment`
    must still cascade correctly if one ever does."""
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)

    from apps.payments import services
    from apps.payments.providers.base import PaymentInitResult
    from apps.payments.providers.mock import MockProvider

    class _InstantSuccessProvider(MockProvider):
        def create_payment(self, ctx):
            return PaymentInitResult(provider_ref="instant_pi_1", state="succeeded")

    monkeypatch.setattr(
        services, "get_provider_for_config", lambda config: _InstantSuccessProvider()
    )

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="instant-success-key",
    )
    assert response.status_code == 201, response.data
    assert response.data["state"] == "succeeded"

    from apps.orders.models import Order
    from apps.payments.tests.conftest import store_db_context

    with store_db_context(ctx["store"]):
        assert Order.objects.get(id=order["id"]).status == Order.Status.CONFIRMED


def test_unknown_order_id_is_404(store_with_hostname, storefront_client):
    import uuid

    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": str(uuid.uuid4()), "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="init-key-unknown",
    )
    assert response.status_code == 404
