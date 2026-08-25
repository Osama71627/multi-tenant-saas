"""`confirm_order`/`cancel_order` -- the seam apps.payments (Phase 9) calls into.
Guards their own precondition directly, independent of any caller."""

from __future__ import annotations

import pytest

from apps.orders import services
from apps.orders.models import Order
from apps.orders.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
)

pytestmark = pytest.mark.django_db


def _make_confirmed_order(ctx, storefront_client) -> Order:
    add_stock(ctx["store"], ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    complete_address_and_shipping(storefront_client, method["id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="lifecycle-fn-key",
    )
    assert response.status_code == 201, response.data
    with store_db_context(ctx["store"]):
        return Order.objects.get(id=response.data["id"])


def test_confirm_order_on_an_already_confirmed_order_raises(variant_in_store, storefront_client):
    ctx = variant_in_store
    order = _make_confirmed_order(ctx, storefront_client)
    with store_db_context(ctx["store"]):
        services.confirm_order(order=order)  # first call: pending_payment -> confirmed
        with pytest.raises(services.OrderNotPendingPaymentError):
            services.confirm_order(order=order)  # second call: already confirmed


def test_cancel_order_on_an_already_confirmed_order_raises(variant_in_store, storefront_client):
    ctx = variant_in_store
    order = _make_confirmed_order(ctx, storefront_client)
    with store_db_context(ctx["store"]):
        services.confirm_order(order=order)
        with pytest.raises(services.OrderNotPendingPaymentError):
            services.cancel_order(order=order)
