from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _adjust(client, store_id, variant_id, location_id, delta, reason="receiving", reference=""):
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/inventory/adjust",
        {
            "variant": variant_id,
            "location": location_id,
            "delta": delta,
            "reason": reason,
            "reference": reference,
        },
        format="json",
    )


def test_no_balance_exists_before_any_adjustment(variant_and_location):
    ctx = variant_and_location
    response = ctx["client"].get(f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/balances")
    assert response.status_code == 200
    assert response.data == []


def test_positive_adjustment_creates_a_balance(variant_and_location):
    ctx = variant_and_location
    response = _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 50)
    assert response.status_code == 200, response.data
    assert response.data["quantity_on_hand"] == 50
    assert response.data["quantity_reserved"] == 0
    assert response.data["quantity_available"] == 50


def test_adjustments_accumulate(variant_and_location):
    ctx = variant_and_location
    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 50)
    response = _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], -10)
    assert response.status_code == 200
    assert response.data["quantity_on_hand"] == 40


def test_adjustment_taking_on_hand_negative_is_rejected(variant_and_location):
    ctx = variant_and_location
    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 10)
    response = _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], -20)
    assert response.status_code == 400

    balances = (
        ctx["client"].get(f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/balances").data
    )
    assert balances[0]["quantity_on_hand"] == 10  # unchanged by the rejected adjustment


def test_low_stock_flag_via_threshold(variant_and_location):
    ctx = variant_and_location
    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 5)

    from apps.inventory.models import StockBalance
    from apps.inventory.tests.conftest import store_db_context

    with store_db_context(ctx["store"]):
        StockBalance.objects.filter(variant_id=ctx["variant_id"]).update(low_stock_threshold=10)

    balances = (
        ctx["client"]
        .get(f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/balances?low_stock=true")
        .data
    )
    assert len(balances) == 1
    assert balances[0]["is_low_stock"] is True


def test_balances_can_be_filtered_by_location(variant_and_location):
    ctx = variant_and_location
    other_location = (
        ctx["client"]
        .post(
            f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/locations",
            {"name": "Second Warehouse"},
            format="json",
        )
        .data
    )

    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 10)
    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], other_location["id"], 20)

    response = ctx["client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/balances?location={other_location['id']}"
    )
    assert len(response.data) == 1
    assert response.data[0]["quantity_on_hand"] == 20


def test_movements_are_recorded_and_listable(variant_and_location):
    ctx = variant_and_location
    _adjust(
        ctx["client"],
        ctx["store"].id,
        ctx["variant_id"],
        ctx["location_id"],
        50,
        reason="initial stock",
    )
    _adjust(
        ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], -5, reason="damaged"
    )

    response = ctx["client"].get(f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/movements")
    assert response.status_code == 200
    assert len(response.data) == 2
    kinds = {m["kind"] for m in response.data}
    assert kinds == {"adjustment"}
    reasons = {m["reason"] for m in response.data}
    assert reasons == {"initial stock", "damaged"}


def test_non_member_cannot_adjust_stock(variant_and_location):
    from apps.inventory.tests.conftest import make_client_for

    ctx = variant_and_location
    outsider_client, _outsider = make_client_for("balance-outsider@example.com")
    response = _adjust(outsider_client, ctx["store"].id, ctx["variant_id"], ctx["location_id"], 50)
    assert response.status_code == 403


def test_adjusting_a_nonexistent_variant_is_404(variant_and_location):
    import uuid

    ctx = variant_and_location
    response = _adjust(ctx["client"], ctx["store"].id, str(uuid.uuid4()), ctx["location_id"], 10)
    assert response.status_code == 404


def test_adjusting_a_nonexistent_location_is_404(variant_and_location):
    import uuid

    ctx = variant_and_location
    response = _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], str(uuid.uuid4()), 10)
    assert response.status_code == 404


def test_balances_can_be_filtered_by_variant(variant_and_location):
    ctx = variant_and_location
    other_product = (
        ctx["client"]
        .post(
            f"/api/v1/dashboard/stores/{ctx['store'].id}/products",
            {"name": "Gadget", "slug": "gadget", "sku": "GADGET-001", "price_amount": 500},
            format="json",
        )
        .data
    )
    other_variant_id = other_product["variants"][0]["id"]

    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 10)
    _adjust(ctx["client"], ctx["store"].id, other_variant_id, ctx["location_id"], 20)

    response = ctx["client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/balances?variant={other_variant_id}"
    )
    assert len(response.data) == 1
    assert response.data[0]["quantity_on_hand"] == 20


def test_movements_can_be_filtered_by_reference_and_variant(variant_and_location):
    ctx = variant_and_location
    _adjust(
        ctx["client"],
        ctx["store"].id,
        ctx["variant_id"],
        ctx["location_id"],
        10,
        reference="po-123",
    )
    _adjust(ctx["client"], ctx["store"].id, ctx["variant_id"], ctx["location_id"], 5)

    by_reference = ctx["client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/movements?reference=po-123"
    )
    assert len(by_reference.data) == 1

    by_variant = ctx["client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/inventory/movements?variant={ctx['variant_id']}"
    )
    assert len(by_variant.data) == 2
