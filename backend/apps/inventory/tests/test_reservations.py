"""
Service-level coverage for reserve/release/fulfill -- no HTTP surface
exists yet (apps/inventory/views.py's docstring explains why), so these
call apps.inventory.services directly, the same way a future Cart/
Checkout service will.
"""

from __future__ import annotations

import pytest

from apps.catalog.models import ProductVariant
from apps.inventory import services
from apps.inventory.models import StockBalance, StockLocation, StockReservation
from apps.inventory.tests.conftest import store_db_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def stocked_variant(variant_and_location):
    ctx = variant_and_location
    with store_db_context(ctx["store"]):
        variant = ProductVariant.objects.get(id=ctx["variant_id"])
        location = StockLocation.objects.get(id=ctx["location_id"])
        services.adjust_stock(
            store=ctx["store"], variant=variant, location=location, delta=20, reason="seed"
        )
    return {**ctx, "variant": variant, "location": location}


def test_reserve_reduces_available_not_on_hand(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        reservation = services.reserve_stock(
            store=ctx["store"],
            variant=ctx["variant"],
            location=ctx["location"],
            quantity=5,
            reference="cart-abc",
        )
        balance = StockBalance.objects.get(variant=ctx["variant"], location=ctx["location"])

    assert reservation.status == StockReservation.Status.ACTIVE
    assert balance.quantity_on_hand == 20
    assert balance.quantity_reserved == 5
    assert balance.quantity_available == 15


def test_reserving_more_than_available_is_rejected(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        with pytest.raises(services.InsufficientStockError):
            services.reserve_stock(
                store=ctx["store"],
                variant=ctx["variant"],
                location=ctx["location"],
                quantity=999,
                reference="cart-too-big",
            )
        balance = StockBalance.objects.get(variant=ctx["variant"], location=ctx["location"])
    assert balance.quantity_reserved == 0  # nothing partially reserved


def test_release_gives_back_availability(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        reservation = services.reserve_stock(
            store=ctx["store"],
            variant=ctx["variant"],
            location=ctx["location"],
            quantity=5,
            reference="cart-release-me",
        )
        services.release_reservation(reservation=reservation)
        balance = StockBalance.objects.get(variant=ctx["variant"], location=ctx["location"])
        reservation.refresh_from_db()

    assert reservation.status == StockReservation.Status.RELEASED
    assert balance.quantity_on_hand == 20
    assert balance.quantity_reserved == 0
    assert balance.quantity_available == 20


def test_fulfill_deducts_from_on_hand_and_clears_reservation(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        reservation = services.reserve_stock(
            store=ctx["store"],
            variant=ctx["variant"],
            location=ctx["location"],
            quantity=5,
            reference="order-42",
        )
        services.fulfill_reservation(reservation=reservation)
        balance = StockBalance.objects.get(variant=ctx["variant"], location=ctx["location"])
        reservation.refresh_from_db()

    assert reservation.status == StockReservation.Status.FULFILLED
    assert balance.quantity_on_hand == 15  # actually sold
    assert balance.quantity_reserved == 0
    assert balance.quantity_available == 15


def test_cannot_release_an_already_released_reservation(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        reservation = services.reserve_stock(
            store=ctx["store"],
            variant=ctx["variant"],
            location=ctx["location"],
            quantity=5,
            reference="cart-double-release",
        )
        services.release_reservation(reservation=reservation)
        with pytest.raises(services.ReservationNotActiveError):
            services.release_reservation(reservation=reservation)


def test_cannot_fulfill_an_already_fulfilled_reservation(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        reservation = services.reserve_stock(
            store=ctx["store"],
            variant=ctx["variant"],
            location=ctx["location"],
            quantity=5,
            reference="order-double-fulfill",
        )
        services.fulfill_reservation(reservation=reservation)
        with pytest.raises(services.ReservationNotActiveError):
            services.fulfill_reservation(reservation=reservation)


def test_every_reservation_lifecycle_step_is_logged_as_a_movement(stocked_variant):
    ctx = stocked_variant
    with store_db_context(ctx["store"]):
        reservation = services.reserve_stock(
            store=ctx["store"],
            variant=ctx["variant"],
            location=ctx["location"],
            quantity=5,
            reference="order-logged",
        )
        services.fulfill_reservation(reservation=reservation)

        from apps.inventory.models import StockMovement

        kinds = list(
            StockMovement.objects.filter(reference="order-logged")
            .order_by("created_at")
            .values_list("kind", flat=True)
        )
    assert kinds == [StockMovement.Kind.RESERVE, StockMovement.Kind.FULFILL]
