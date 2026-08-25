"""
Business logic for stock adjustments, reservations, and releases. Kept
out of views per docs/ARCHITECTURE.md section 11 -- the invariants here
(row-locked balance mutation, ledger append, no-overselling) are exactly
the kind of thing that must not live in a View.

Every mutating function here follows the same shape: open
`transaction.atomic()`, `select_for_update()` the `StockBalance` row (or
create it if this is the first movement for that variant/location pair),
mutate the in-memory counters, save, then append a `StockMovement` row
in the same transaction. `select_for_update()` scopes the lock to that
one (variant, location) row -- concurrent operations on a DIFFERENT
variant or location never block each other. The three CHECK constraints
on `StockBalance` (apps/inventory/models.py) are the actual, DB-enforced
backstop against overselling: even a bug in this file's logic cannot
produce a negative or over-reserved balance, it can only make the
`INSERT`/`UPDATE` fail.
"""

from __future__ import annotations

from django.db import transaction

from apps.catalog.models import ProductVariant
from apps.inventory.models import StockBalance, StockLocation, StockMovement, StockReservation
from apps.stores.models import Store


class InsufficientStockError(Exception):
    """Not enough available (on_hand - reserved) stock to satisfy a reservation."""


class ReservationNotActiveError(Exception):
    """A release/fulfill was attempted on a reservation that isn't `active`."""


def create_location(*, store: Store, name: str) -> StockLocation:
    return StockLocation.objects.create(store=store, name=name)


def _locked_or_new_balance(
    *, store: Store, variant: ProductVariant, location: StockLocation
) -> StockBalance:
    """Must be called inside an open `transaction.atomic()` block."""
    balance, _created = StockBalance.objects.select_for_update().get_or_create(
        store=store, variant=variant, location=location
    )
    return balance


def _record_movement(
    *,
    store: Store,
    variant: ProductVariant,
    location: StockLocation,
    kind: str,
    delta_on_hand: int,
    delta_reserved: int,
    balance: StockBalance,
    reference: str = "",
    reason: str = "",
) -> StockMovement:
    return StockMovement.objects.create(
        store=store,
        variant=variant,
        location=location,
        kind=kind,
        delta_on_hand=delta_on_hand,
        delta_reserved=delta_reserved,
        balance_on_hand_after=balance.quantity_on_hand,
        balance_reserved_after=balance.quantity_reserved,
        reference=reference,
        reason=reason,
    )


def adjust_stock(
    *,
    store: Store,
    variant: ProductVariant,
    location: StockLocation,
    delta: int,
    reason: str,
    reference: str = "",
) -> StockBalance:
    """
    Manual stock adjustment (receiving, damage write-off, recount, ...).
    `delta` may be negative; the `quantity_on_hand >= 0` CHECK
    constraint is what actually prevents an adjustment from taking a
    balance negative, not a Python-level guard here.
    """
    with transaction.atomic(using="default"):
        balance = _locked_or_new_balance(store=store, variant=variant, location=location)
        balance.quantity_on_hand += delta
        balance.save(update_fields=["quantity_on_hand", "updated_at"])
        _record_movement(
            store=store,
            variant=variant,
            location=location,
            kind=StockMovement.Kind.ADJUSTMENT,
            delta_on_hand=delta,
            delta_reserved=0,
            balance=balance,
            reference=reference,
            reason=reason,
        )
    return balance


def reserve_stock(
    *,
    store: Store,
    variant: ProductVariant,
    location: StockLocation,
    quantity: int,
    reference: str,
    expires_at=None,
) -> StockReservation:
    """
    Raises `InsufficientStockError` (application-level, friendly) if
    `quantity_available < quantity` at lock-acquisition time -- but the
    REAL guarantee against overselling under concurrency is the
    `stockbalance_reserved_not_exceeding_on_hand` CHECK constraint plus
    `select_for_update()` serializing concurrent attempts on this exact
    (variant, location) row: two simultaneous requests for the last unit
    can never both succeed, because the second one's `select_for_update()`
    blocks until the first's transaction commits (or rolls back), and by
    then the balance it reads is already up to date.
    """
    with transaction.atomic(using="default"):
        balance = _locked_or_new_balance(store=store, variant=variant, location=location)
        if balance.quantity_available < quantity:
            raise InsufficientStockError(
                f"requested {quantity}, only {balance.quantity_available} available"
            )
        balance.quantity_reserved += quantity
        balance.save(update_fields=["quantity_reserved", "updated_at"])
        _record_movement(
            store=store,
            variant=variant,
            location=location,
            kind=StockMovement.Kind.RESERVE,
            delta_on_hand=0,
            delta_reserved=quantity,
            balance=balance,
            reference=reference,
        )
        reservation = StockReservation.objects.create(
            store=store,
            variant=variant,
            location=location,
            quantity=quantity,
            reference=reference,
            status=StockReservation.Status.ACTIVE,
            expires_at=expires_at,
        )
    return reservation


def release_reservation(*, reservation: StockReservation) -> StockReservation:
    """
    Gives the reservation's quantity back to `available`; `on_hand`
    is untouched -- nothing was actually sold.
    """
    if reservation.status != StockReservation.Status.ACTIVE:
        raise ReservationNotActiveError(f"reservation is {reservation.status}, not active")

    with transaction.atomic(using="default"):
        balance = StockBalance.objects.select_for_update().get(
            store=reservation.store, variant=reservation.variant, location=reservation.location
        )
        balance.quantity_reserved -= reservation.quantity
        balance.save(update_fields=["quantity_reserved", "updated_at"])
        _record_movement(
            store=reservation.store,
            variant=reservation.variant,
            location=reservation.location,
            kind=StockMovement.Kind.RELEASE,
            delta_on_hand=0,
            delta_reserved=-reservation.quantity,
            balance=balance,
            reference=reservation.reference,
        )
        reservation.status = StockReservation.Status.RELEASED
        reservation.save(update_fields=["status", "updated_at"])
    return reservation


def fulfill_reservation(*, reservation: StockReservation) -> StockReservation:
    """Converts a reservation into a sale: deducts `on_hand` AND clears the `reserved` hold."""
    if reservation.status != StockReservation.Status.ACTIVE:
        raise ReservationNotActiveError(f"reservation is {reservation.status}, not active")

    with transaction.atomic(using="default"):
        balance = StockBalance.objects.select_for_update().get(
            store=reservation.store, variant=reservation.variant, location=reservation.location
        )
        balance.quantity_on_hand -= reservation.quantity
        balance.quantity_reserved -= reservation.quantity
        balance.save(update_fields=["quantity_on_hand", "quantity_reserved", "updated_at"])
        _record_movement(
            store=reservation.store,
            variant=reservation.variant,
            location=reservation.location,
            kind=StockMovement.Kind.FULFILL,
            delta_on_hand=-reservation.quantity,
            delta_reserved=-reservation.quantity,
            balance=balance,
            reference=reservation.reference,
        )
        reservation.status = StockReservation.Status.FULFILLED
        reservation.save(update_fields=["status", "updated_at"])
    return reservation
