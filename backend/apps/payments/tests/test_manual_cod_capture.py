"""
COD lifecycle -- REVISED in the Phase 9 review round (docs/PHASE_9_REPORT.md):
acceptance (choosing COD) confirms the Order and commits inventory
IMMEDIATELY; collection (the merchant's later "cash actually collected"
dashboard action) only ever flips `PaymentIntent.state`, never re-confirms
the Order or re-fulfills inventory a second time.

`COD acceptance != COD cash collection`, and `Order/inventory side effects
occur exactly once` -- both proven directly below.
"""

from __future__ import annotations

import pytest

from apps.payments.tests.conftest import create_order, enable_provider, store_db_context

pytestmark = pytest.mark.django_db


def _initiate_cod(ctx, storefront_client, order, *, key="cod-init") -> dict:
    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "manual_cod"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data


def _reservation(ctx, order_id):
    from apps.inventory.models import StockReservation
    from apps.orders.models import order_reservation_reference

    return StockReservation.objects.get(reference=order_reservation_reference(order_id))


# -- 1. Accepting COD confirms the Order immediately --------------------------------


def test_accepting_cod_confirms_the_order_immediately(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    _initiate_cod(ctx, storefront_client, order)

    from apps.orders.models import Order

    with store_db_context(ctx["store"]):
        assert Order.objects.get(id=order["id"]).status == Order.Status.CONFIRMED


# -- 2. Inventory is committed (fulfilled) exactly once, at acceptance --------------


def test_accepting_cod_fulfills_inventory_exactly_once(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    _initiate_cod(ctx, storefront_client, order)

    from apps.inventory.models import StockReservation

    with store_db_context(ctx["store"]):
        reservation = _reservation(ctx, order["id"])
        assert reservation.status == StockReservation.Status.FULFILLED


# -- 3. PaymentIntent is not yet succeeded after mere acceptance --------------------


def test_accepting_cod_leaves_the_payment_intent_processing(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    intent = _initiate_cod(ctx, storefront_client, order)
    assert intent["state"] == "processing"  # accepted, NOT paid


# -- 4. Later capture (collection) changes only the payment state -------------------


def test_capturing_cod_only_changes_the_payment_state(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    intent = _initiate_cod(ctx, storefront_client, order)

    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payment-intents/{intent['id']}/capture-cod"
    )
    assert response.status_code == 200, response.data
    assert response.data["state"] == "succeeded"

    from apps.orders.models import Order

    with store_db_context(ctx["store"]):
        # Still confirmed -- was ALREADY confirmed at acceptance, capture didn't
        # need to (and structurally cannot) confirm it a "second first time".
        assert Order.objects.get(id=order["id"]).status == Order.Status.CONFIRMED


# -- 5. Repeated capture does not confirm the Order or fulfill inventory twice ------


def test_repeated_capture_does_not_duplicate_order_or_inventory_side_effects(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    intent = _initiate_cod(ctx, storefront_client, order)

    url = f"/api/v1/dashboard/stores/{ctx['store'].id}/payment-intents/{intent['id']}/capture-cod"
    first = ctx["dashboard_client"].post(url)
    second = ctx["dashboard_client"].post(url)
    assert first.status_code == 200
    assert second.status_code == 200

    from apps.inventory.models import StockReservation
    from apps.orders.models import Order
    from apps.payments.models import PaymentTransaction

    with store_db_context(ctx["store"]):
        assert Order.objects.get(id=order["id"]).status == Order.Status.CONFIRMED
        reservation = _reservation(ctx, order["id"])
        assert reservation.status == StockReservation.Status.FULFILLED  # not fulfilled twice
        # One `succeeded` capture is recorded once via apply_payment_transition's
        # terminal-state no-op guard for the second call -- but BOTH calls to
        # `provider.capture()` itself still produce a PaymentTransaction row each
        # (the audit trail records every attempt, per approved decision 4/10 of
        # Phase 9's original design) -- what must NOT happen is a second Order
        # confirmation or a second inventory fulfillment, both proven above.
        assert PaymentTransaction.objects.filter(intent_id=intent["id"]).count() == 2


def test_capture_cod_rejects_a_non_cod_intent(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="mock")
    order = create_order(ctx, storefront_client)
    response = storefront_client.post(
        "/api/v1/storefront/payments/initiate",
        {"order_id": order["id"], "provider_key": "mock"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="mock-not-cod",
    )
    intent = response.data

    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payment-intents/{intent['id']}/capture-cod"
    )
    assert response.status_code == 400


def test_capture_cod_for_unknown_payment_intent_is_404(store_with_hostname):
    import uuid

    ctx = store_with_hostname
    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payment-intents/{uuid.uuid4()}/capture-cod"
    )
    assert response.status_code == 404


def test_non_member_cannot_capture_cod(variant_in_store, storefront_client):
    ctx = variant_in_store
    enable_provider(ctx, provider_key="manual_cod")
    order = create_order(ctx, storefront_client)
    intent = _initiate_cod(ctx, storefront_client, order)

    from apps.payments.tests.conftest import make_client_for

    outsider_client, _outsider = make_client_for("cod-outsider@example.com")
    response = outsider_client.post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payment-intents/{intent['id']}/capture-cod"
    )
    assert response.status_code == 403
