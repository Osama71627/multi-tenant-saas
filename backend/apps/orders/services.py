"""
Checkout orchestration. Kept out of views per docs/ARCHITECTURE.md
section 11, same as every prior app.

`checkout_complete` is the one function in this project so far that
composes FOUR other apps' primitives inside a single atomic transaction
(pricing, shipping, inventory, carts) without duplicating any of their
logic -- see this module's docstring on each step below for exactly
which existing function is being reused and why nothing here is a
second implementation of pricing/shipping/inventory rules.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from apps.carts.models import Cart, CartItem
from apps.catalog.models import ProductVariant
from apps.core.events import emit_domain_event
from apps.inventory import services as inventory_services
from apps.inventory.models import StockLocation, StockReservation
from apps.orders.models import (
    CheckoutSession,
    IdempotencyKey,
    Order,
    OrderItem,
    OrderNumberSequence,
    order_reservation_reference,
)
from apps.pricing.calculator import calculate_totals
from apps.pricing.models import Coupon, TaxRate
from apps.pricing.services import CouponInvalidError, validate_coupon
from apps.shipping import services as shipping_services
from apps.stores.models import Store
from apps.subscriptions import entitlements

_CHECKOUT_SESSION_TTL = timedelta(minutes=30)


class EmptyCartError(Exception):
    pass


class NoActiveCheckoutSessionError(Exception):
    """No `CheckoutSession` in `active` status exists for this cart (never started, already
    completed, or superseded)."""


class CheckoutSessionExpiredError(Exception):
    pass


class CheckoutStepIncompleteError(Exception):
    """A required prior step (address before shipping, address+shipping before complete)
    hasn't been completed on this session yet."""


class ShippingMethodNotAvailableError(Exception):
    """The chosen shipping method isn't among the CURRENT authoritative quotes for this
    session's address/cart -- raised both at the `shipping` step (soft, for fast feedback)
    and re-raised at `complete` (authoritative, never trusts the earlier check)."""


class CartRevalidationError(Exception):
    """A cart line's variant is no longer purchasable (archived/draft) at commit time."""


class CouponRevalidationError(Exception):
    """The cart's applied coupon is no longer valid at commit time (inactive, expired,
    exhausted, or currency mismatch) -- see `apps.pricing.services.validate_coupon`."""


class CheckoutInventoryError(Exception):
    """No `StockLocation` can satisfy one of this order's lines in full (Phase 8 decision
    6: no cross-location split allocation -- see apps/orders/models.py's module docstring)."""


class IdempotencyKeyRequiredError(Exception):
    pass


class IdempotencyConflictError(Exception):
    """Same `Idempotency-Key` reused for a materially different request (different cart/session)."""


class OrderNotPendingPaymentError(Exception):
    """`confirm_order`/`cancel_order` were called on an Order that isn't (or is no longer)
    `pending_payment` -- the Order FSM only allows leaving that state once, in one direction."""


@dataclass(frozen=True, slots=True)
class CheckoutCompleteResult:
    response_status: int
    response_body: dict
    created: bool


def get_active_checkout_session(*, cart: Cart) -> CheckoutSession:
    try:
        session = CheckoutSession.objects.get(cart=cart, status=CheckoutSession.Status.ACTIVE)
    except CheckoutSession.DoesNotExist as exc:
        raise NoActiveCheckoutSessionError("No active checkout session for this cart.") from exc
    if session.expires_at <= timezone.now():
        raise CheckoutSessionExpiredError("This checkout session has expired.")
    return session


def start_checkout(*, cart: Cart) -> CheckoutSession:
    """Idempotent-ish: reuses an existing active, unexpired session for this cart instead of
    creating a duplicate (the partial unique constraint on `CheckoutSession` would reject a
    second ACTIVE row for the same cart anyway -- this just avoids hitting that as an error)."""
    if not CartItem.objects.filter(cart=cart).exists():
        raise EmptyCartError("Cannot start checkout with an empty cart.")

    try:
        existing = get_active_checkout_session(cart=cart)
    except (NoActiveCheckoutSessionError, CheckoutSessionExpiredError):
        existing = None
    if existing is not None:
        return existing

    return CheckoutSession.objects.create(
        store=cart.store, cart=cart, expires_at=timezone.now() + _CHECKOUT_SESSION_TTL
    )


def set_checkout_address(
    *, session: CheckoutSession, email: str, shipping_address: dict
) -> CheckoutSession:
    session.email = email
    session.shipping_address = shipping_address
    session.save(update_fields=["email", "shipping_address", "updated_at"])
    return session


def set_checkout_shipping(*, session: CheckoutSession, shipping_method_id) -> CheckoutSession:
    if not session.shipping_address:
        raise CheckoutStepIncompleteError("Set the address before choosing a shipping method.")

    items = [
        (item.variant, item.quantity)
        for item in CartItem.objects.filter(cart=session.cart).select_related("variant")
    ]
    quotes = shipping_services.get_quotes_for_destination(
        store=session.store,
        country_code=session.shipping_address["country_code"],
        region=session.shipping_address.get("region", ""),
        postal_code=session.shipping_address.get("postal_code", ""),
        items=items,
        subtotal_amount=sum(v.price_amount * q for v, q in items),
    )
    matched = next((q for q in quotes if str(q.method_id) == str(shipping_method_id)), None)
    if matched is None:
        raise ShippingMethodNotAvailableError("This shipping method is not currently available.")

    session.shipping_method_id = shipping_method_id
    session.shipping_method_name_snapshot = matched.method_name
    session.shipping_amount_snapshot = matched.price_amount
    session.save(
        update_fields=[
            "shipping_method",
            "shipping_method_name_snapshot",
            "shipping_amount_snapshot",
            "updated_at",
        ]
    )
    return session


def _variant_is_purchasable(variant: ProductVariant) -> bool:
    """Mirrors `apps.carts.services._is_purchasable` -- duplicated rather than imported
    because that helper is module-private by convention; the check itself is 2 lines."""
    return (
        variant.status == ProductVariant.Status.ACTIVE
        and variant.product.status == variant.product.Status.ACTIVE
    )


def _reserve_item_stock(*, store: Store, variant: ProductVariant, quantity: int, order_id) -> None:
    """
    Tries each active `StockLocation` in a deterministic order (`id` --
    UUIDv7, creation order) until one has enough available stock to
    satisfy the FULL quantity (approved Phase 8 decision 6: no
    cross-location split allocation -- a line that needs splitting is
    InsufficientStock in Phase 8, not partially fulfilled).

    Calling `inventory_services.reserve_stock` and catching its
    `InsufficientStockError` is safe to retry against the next
    candidate location: `reserve_stock` opens its own `atomic()` block,
    which -- nested inside this function's caller's already-open
    transaction -- becomes a SAVEPOINT. An exception raised inside it
    rolls back only that savepoint (including any zero-balance
    `StockBalance` row its own `get_or_create` may have inserted for a
    location with no prior stock history), leaving the outer checkout
    transaction untouched. This is standard Django `atomic()` nesting,
    not special-cased error handling.
    """
    last_error: Exception | None = None
    for location in StockLocation.objects.filter(is_active=True).order_by("id"):
        try:
            inventory_services.reserve_stock(
                store=store,
                variant=variant,
                location=location,
                quantity=quantity,
                reference=order_reservation_reference(order_id),
            )
            return
        except inventory_services.InsufficientStockError as exc:
            last_error = exc
            continue
    raise CheckoutInventoryError(
        f"Not enough stock for {variant.sku} ({quantity} requested)."
    ) from last_error


def _option_snapshot(variant: ProductVariant) -> list[dict[str, str]]:
    """Human-readable `[{"option": "Color", "value": "Red"}, ...]` -- NOT
    `ProductVariant.option_signature` (a raw array of `ProductOptionValue` UUIDs, meant only
    for the DB uniqueness constraint in apps.catalog, not for snapshotting: those rows can be
    edited/deleted later, which would silently corrupt a historical Order's line description)."""
    return [
        {"option": ov.option.name, "value": ov.option_value.value}
        for ov in variant.option_values.select_related("option", "option_value").order_by(
            "option__id"
        )
    ]


def _next_order_number(*, store: Store) -> str:
    sequence, _created = OrderNumberSequence.objects.select_for_update().get_or_create(store=store)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number", "updated_at"])
    return f"ORD-{sequence.last_number:06d}"


def _fingerprint_for_session_id(session_id) -> str:
    """A session is single-use (flipped to `completed` inside the same transaction that
    creates its Order), so its id alone uniquely identifies "this exact checkout attempt" --
    reusing the same Idempotency-Key for a DIFFERENT session (different cart/intent) must
    fingerprint differently, which this satisfies. Takes the id directly (not the session
    instance) because `checkout_complete` must compute this BEFORE deciding whether to
    lock/re-fetch the session at all (see that function's docstring)."""
    return hashlib.sha256(str(session_id).encode()).hexdigest()


def _build_order(*, session: CheckoutSession, store: Store) -> Order:
    """Must be called inside an open `transaction.atomic()` block. Re-derives and
    re-validates EVERYTHING from current authoritative state -- never trusts `CartItem`
    price snapshots, the session's shipping snapshot, or prior coupon/stock checks
    (approved Phase 8 decisions 4 and 9).

    Phase 10 additions, both inside this SAME transaction as the Order
    row they guard: `require_active_store` rejects purchase on a
    `read_only` Store (approved architecture decision 11 -- "المتجر يظل
    يقبل التصفّح ويوقف الشراء"); `check_quota` enforces the
    `orders_per_period` quota via a `UsageRecord` row lock (approved
    architecture decision 5/9 -- Order rows are immutable/append-only, so
    a maintained counter can never drift from reality). Both run exactly
    once per successful checkout no matter how many times a client
    retries the SAME Idempotency-Key: `checkout_complete`'s idempotency
    claim (below) means a replayed request never re-enters this function
    at all -- see apps/orders/tests/test_quota_idempotency.py.
    """
    entitlements.require_active_store(store=store)
    entitlements.check_quota(store=store, quota_key="orders_per_period")

    if not session.shipping_address:
        raise CheckoutStepIncompleteError("Address step not completed.")
    if not session.shipping_method_id:
        raise CheckoutStepIncompleteError("Shipping step not completed.")

    cart_items = list(
        CartItem.objects.select_for_update()
        .filter(cart=session.cart)
        .select_related("variant", "variant__product")
    )
    if not cart_items:
        raise EmptyCartError("Cannot complete checkout with an empty cart.")

    for item in cart_items:
        if not _variant_is_purchasable(item.variant):
            raise CartRevalidationError(
                f"{item.variant.sku} is no longer available and must be removed from the cart."
            )

    # Authoritative price: current `ProductVariant.price_amount`, never the possibly-stale
    # `CartItem.unit_price_amount` snapshot (approved Phase 8 decision 9).
    subtotal_amount = sum(item.variant.price_amount * item.quantity for item in cart_items)

    coupon: Coupon | None = None
    if session.cart.coupon_id:
        coupon = Coupon.objects.select_for_update().get(id=session.cart.coupon_id)
        try:
            validate_coupon(coupon, currency=session.cart.currency)
        except CouponInvalidError as exc:
            raise CouponRevalidationError(str(exc)) from exc

    tax_rate = TaxRate.objects.filter(is_active=True).first()
    totals = calculate_totals(subtotal_amount=subtotal_amount, coupon=coupon, tax_rate=tax_rate)

    items_for_shipping = [(item.variant, item.quantity) for item in cart_items]
    quotes = shipping_services.get_quotes_for_destination(
        store=store,
        country_code=session.shipping_address["country_code"],
        region=session.shipping_address.get("region", ""),
        postal_code=session.shipping_address.get("postal_code", ""),
        items=items_for_shipping,
        subtotal_amount=totals.subtotal_amount,
    )
    matched_quote = next(
        (q for q in quotes if str(q.method_id) == str(session.shipping_method_id)), None
    )
    if matched_quote is None:
        raise ShippingMethodNotAvailableError(
            "The chosen shipping method is no longer available for this order."
        )
    shipping_amount = matched_quote.price_amount
    total_amount = totals.total_amount + shipping_amount

    order = Order.objects.create(
        store=store,
        number=_next_order_number(store=store),
        email=session.email,
        currency=session.cart.currency,
        subtotal_amount=totals.subtotal_amount,
        discount_amount=totals.discount_amount,
        tax_amount=totals.tax_amount,
        shipping_amount=shipping_amount,
        total_amount=total_amount,
        shipping_address=session.shipping_address,
        shipping_method_name_snapshot=matched_quote.method_name,
        coupon_code_snapshot=coupon.code if coupon else "",
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                store=store,
                order=order,
                variant=item.variant,
                variant_name_snapshot=item.variant.product.name,
                variant_sku_snapshot=item.variant.sku,
                variant_options_snapshot=_option_snapshot(item.variant),
                unit_price_amount=item.variant.price_amount,
                quantity=item.quantity,
                currency=item.variant.currency,
            )
            for item in cart_items
        ]
    )

    for item in cart_items:
        _reserve_item_stock(
            store=store, variant=item.variant, quantity=item.quantity, order_id=order.id
        )

    if coupon is not None:
        coupon.times_used += 1
        coupon.save(update_fields=["times_used", "updated_at"])

    session.status = CheckoutSession.Status.COMPLETED
    session.save(update_fields=["status", "updated_at"])

    return order


def checkout_complete(
    *, cart: Cart, store: Store, idempotency_key: str, order_serializer_cls
) -> CheckoutCompleteResult:
    """
    `(store, key)` uniqueness on `IdempotencyKey` is the actual
    correctness boundary (docs/PHASE_8_REPORT.md, not Redis): the
    `try: create() / except IntegrityError: get()` pattern below is
    safe under real concurrency because Postgres blocks a second
    INSERT on a matching unique key until the FIRST transaction commits
    or rolls back -- by the time the blocked INSERT is released and
    fails with `IntegrityError`, the winning row's final state
    (`completed`, response populated) is already fully committed and
    visible. There is no window where a concurrent reader can observe
    a `pending` row from another transaction; Postgres MVCC only
    exposes the pre-transaction or post-commit state, never a
    mid-transaction one.

    That boundary alone only rules out reuse of the SAME key. It does
    NOT rule out two concurrent requests with DIFFERENT keys against
    the SAME (still-`active`-looking) `CheckoutSession` -- the
    `CheckoutSession.objects.select_for_update()` re-fetch below,
    inside this same transaction, is what actually closes that: a
    second concurrent attempt blocks on that row lock until the first
    commits, then sees the now-`completed` status and is rejected. The
    single-order-per-session invariant is therefore DB-lock-backed, not
    dependent on the idempotency key matching (docs/PHASE_8_REPORT.md
    addendum on the "different keys, same session" race).
    """
    if not idempotency_key:
        raise IdempotencyKeyRequiredError("Idempotency-Key header is required.")

    try:
        session_id = CheckoutSession.objects.filter(cart=cart).latest("created_at").id
    except CheckoutSession.DoesNotExist as exc:
        raise NoActiveCheckoutSessionError("No checkout session for this cart.") from exc

    fingerprint = _fingerprint_for_session_id(session_id)

    with transaction.atomic(using="default"):
        try:
            with transaction.atomic(using="default"):
                idem = IdempotencyKey.objects.create(
                    store=store,
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    status=IdempotencyKey.Status.PENDING,
                )
        except IntegrityError:
            existing = IdempotencyKey.objects.select_for_update().get(
                store=store, key=idempotency_key
            )
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError(
                    "This Idempotency-Key was already used for a different checkout."
                ) from None
            if existing.status != IdempotencyKey.Status.COMPLETED:
                # Unreachable under normal Postgres MVCC (see docstring) --
                # guarded, not silently trusted.
                raise IdempotencyConflictError(
                    "This Idempotency-Key is still being processed."
                ) from None
            return CheckoutCompleteResult(
                response_status=existing.response_status,
                response_body=existing.response_body,
                created=False,
            )

        # Re-fetch AND LOCK the session now, inside the transaction -- never trust the
        # unlocked read used only to compute `fingerprint` above. This is the actual
        # single-order-per-session gate (see this function's docstring).
        session = CheckoutSession.objects.select_for_update().get(id=session_id)
        if session.status != CheckoutSession.Status.ACTIVE:
            raise NoActiveCheckoutSessionError("This checkout session is no longer active.")
        if session.expires_at <= timezone.now():
            raise CheckoutSessionExpiredError("This checkout session has expired.")

        order = _build_order(session=session, store=store)

        body = json.loads(JSONRenderer().render(order_serializer_cls(order).data))
        idem.status = IdempotencyKey.Status.COMPLETED
        idem.response_status = 201
        idem.response_body = body
        idem.save(update_fields=["status", "response_status", "response_body", "updated_at"])

    return CheckoutCompleteResult(response_status=201, response_body=body, created=True)


def confirm_order(*, order: Order) -> Order:
    """
    The only sanctioned way for ANY caller (apps.payments today; a future
    manual dashboard override tomorrow) to move an Order out of
    `pending_payment` into `confirmed`. Locks the row and re-checks its
    CURRENT status rather than trusting whatever the caller's own object
    holds -- same discipline as `CheckoutSession.objects.select_for_update()`
    in `checkout_complete` (docs/PHASE_8_REPORT.md's review-round fix) --
    so two concurrent callers can never both apply this.

    Must be called inside an already-open `transaction.atomic()` block
    (the caller is expected to have already locked whatever prompted this
    -- e.g. a `PaymentIntent` row -- establishing a single, consistent
    lock order: PaymentIntent before Order, never the reverse, everywhere
    in this codebase).

    "Confirmed" means the sale is real, independent of why (payment
    success today) -- so fulfilling this Order's inventory reservations
    (converting the hold into an actual `on_hand` deduction) belongs here,
    not duplicated in every caller.

    Also emits the `order.confirmed` Domain Event (approved Phase 11
    decision) -- inside this SAME transaction, so a rolled-back
    confirmation never leaves a committed event behind. This is the
    ONLY place that event is emitted: every caller (payment success
    today, a future manual override) reaches this one function, so
    "one authoritative transition" gives "one authoritative domain
    event" for free, with no per-caller duplication. `apps.orders` never
    imports `apps.notifications` to do this -- `emit_domain_event`
    (apps.core, a lower layer) is the only thing referenced; see that
    module's docstring for the full reasoning (Django Signals are
    forbidden in this critical path per docs/ARCHITECTURE.md line 107).
    """
    locked = Order.objects.select_for_update().get(id=order.id)
    if locked.status != Order.Status.PENDING_PAYMENT:
        raise OrderNotPendingPaymentError(
            f"Order {locked.number} is {locked.status}, not pending_payment."
        )
    locked.status = Order.Status.CONFIRMED
    locked.save(update_fields=["status", "updated_at"])

    reservations = StockReservation.objects.filter(
        reference=order_reservation_reference(locked.id), status=StockReservation.Status.ACTIVE
    )
    for reservation in reservations:
        inventory_services.fulfill_reservation(reservation=reservation)

    emit_domain_event(
        event_type="order.confirmed",
        store_id=locked.store_id,
        aggregate_type="order",
        aggregate_id=locked.id,
        payload={"order_number": locked.number},
    )

    return locked


def cancel_order(*, order: Order) -> Order:
    """Mirror of `confirm_order` for the failure path: releases (not fulfills) this
    Order's active reservations. Same locking discipline, same calling convention."""
    locked = Order.objects.select_for_update().get(id=order.id)
    if locked.status != Order.Status.PENDING_PAYMENT:
        raise OrderNotPendingPaymentError(
            f"Order {locked.number} is {locked.status}, not pending_payment."
        )
    locked.status = Order.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])

    reservations = StockReservation.objects.filter(
        reference=order_reservation_reference(locked.id), status=StockReservation.Status.ACTIVE
    )
    for reservation in reservations:
        inventory_services.release_reservation(reservation=reservation)
    return locked
