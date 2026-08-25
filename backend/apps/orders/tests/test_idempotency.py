"""HTTP-level idempotency behavior (sequential -- real concurrent-connection proof is
apps/orders/tests/test_concurrency.py::test_same_idempotency_key_concurrent_requests_yield_exactly_one_order).
docs/ARCHITECTURE.md section 5.2 mandates the `Idempotency-Key` header on
`checkout/complete`."""

from __future__ import annotations

import pytest

from apps.orders.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
)

pytestmark = pytest.mark.django_db


def _prepare(ctx, storefront_client):
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])


def test_repeating_the_same_idempotency_key_replays_the_same_order(
    variant_in_store, storefront_client
):
    _prepare(variant_in_store, storefront_client)

    first = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="repeat-key",
    )
    second = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="repeat-key",
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["id"] == second.data["id"]
    assert first.data["number"] == second.data["number"]

    from apps.orders.models import Order
    from apps.orders.tests.conftest import store_db_context

    with store_db_context(variant_in_store["store"]):
        assert Order.objects.filter(number=first.data["number"]).count() == 1


def test_reusing_the_same_key_for_a_different_checkout_session_is_a_conflict(
    variant_in_store, storefront_client
):
    _prepare(variant_in_store, storefront_client)
    first = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="shared-key",
    )
    assert first.status_code == 201

    # A brand new cart/checkout session (different browser/tab) reusing the SAME
    # Idempotency-Key must be rejected, never silently replay the unrelated order.
    # `_prepare` already stocked 10 units and the first checkout only reserved 1.
    from django.test import Client

    class FreshClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", variant_in_store["hostname"])
            return super().generic(method, path, *args, **kwargs)

    fresh_client = FreshClient()  # no cookies shared -- a genuinely different cart
    method_response = variant_in_store["dashboard_client"].get(
        f"/api/v1/dashboard/stores/{variant_in_store['store'].id}/shipping/zones"
    )
    zone_id = method_response.data[0]["id"]
    method_id = (
        variant_in_store["dashboard_client"]
        .get(
            f"/api/v1/dashboard/stores/{variant_in_store['store'].id}/shipping/zones/{zone_id}/methods"
        )
        .data[0]["id"]
    )

    add_item_and_start_checkout(fresh_client, variant_in_store["variant_id"])
    complete_address_and_shipping(fresh_client, method_id)

    second = fresh_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="shared-key",
    )
    assert second.status_code == 409
