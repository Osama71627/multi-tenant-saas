"""
Cart business logic. Kept out of views per docs/ARCHITECTURE.md section
11. `reprice_cart` is the DoD-critical operation for this phase --
"إعادة تسعير كاملة على الخادم" -- everything else here (`add_item`,
`update_item_quantity`, `remove_item`, `apply_coupon`, `remove_coupon`)
calls `recalculate_totals` at the end so `Cart`'s snapshot totals are
always in sync with its own current contents, using each `CartItem`'s
EXISTING price snapshot -- `recalculate_totals` never touches the
catalog itself. Only `reprice_cart` refreshes those snapshots from
`ProductVariant`'s current state.
"""

from __future__ import annotations

from django.db import transaction

from apps.carts.models import Cart, CartItem
from apps.catalog.models import ProductVariant
from apps.core.tokens import generate_raw_token, hash_raw_token
from apps.pricing.calculator import calculate_totals
from apps.pricing.models import Coupon, TaxRate
from apps.pricing.services import validate_coupon
from apps.stores.models import Store


class VariantNotAvailableError(Exception):
    """The variant is archived (or otherwise not purchasable) -- can't be added to a cart."""


class CurrencyMismatchError(Exception):
    """A variant's currency doesn't match the cart's -- see the note on single-currency v1 above."""


class CouponNotFoundError(Exception):
    pass


def get_or_create_cart(*, store: Store, raw_token: str | None) -> tuple[Cart, str]:
    """
    Returns `(cart, raw_token)`. If `raw_token` resolves to an existing
    active cart FOR THIS STORE (RLS-scoped `Cart.objects`, per the
    already-resolved tenant context -- a token valid for a different
    store is simply invisible here, not a special case to handle), reuse
    it and return the same token unchanged. Otherwise mint a brand new
    cart + token. The view is responsible for setting the token cookie.
    """
    if raw_token:
        try:
            cart = Cart.objects.get(token_hash=hash_raw_token(raw_token), status=Cart.Status.ACTIVE)
            return cart, raw_token
        except Cart.DoesNotExist:
            pass

    new_raw_token = generate_raw_token()
    cart = Cart.objects.create(
        store=store, token_hash=hash_raw_token(new_raw_token), currency=store.default_currency
    )
    return cart, new_raw_token


def recalculate_totals(cart: Cart) -> Cart:
    """
    Sums `cart`'s EXISTING `CartItem` price snapshots (does not touch
    the catalog) -- called after every mutation so `Cart`'s stored
    totals never drift from its own contents.
    """
    with transaction.atomic(using="default"):
        locked_cart = Cart.objects.select_for_update().get(id=cart.id)
        subtotal_amount = sum(
            item.unit_price_amount * item.quantity
            for item in CartItem.objects.filter(cart=locked_cart)
        )
        tax_rate = TaxRate.objects.filter(is_active=True).first()
        totals = calculate_totals(
            subtotal_amount=subtotal_amount, coupon=locked_cart.coupon, tax_rate=tax_rate
        )
        locked_cart.subtotal_amount = totals.subtotal_amount
        locked_cart.discount_amount = totals.discount_amount
        locked_cart.tax_amount = totals.tax_amount
        locked_cart.total_amount = totals.total_amount
        locked_cart.save(
            update_fields=[
                "subtotal_amount",
                "discount_amount",
                "tax_amount",
                "total_amount",
                "updated_at",
            ]
        )
    return locked_cart


def _is_purchasable(variant: ProductVariant) -> bool:
    """Both the variant AND its parent Product must be active -- a draft/archived
    product's variants default to `status=active` at the row level (Phase 4), so
    checking the variant alone would let an unpublished product slip into a cart."""
    return (
        variant.status == ProductVariant.Status.ACTIVE
        and variant.product.status == variant.product.Status.ACTIVE
    )


def add_item(*, cart: Cart, variant: ProductVariant, quantity: int) -> CartItem:
    if not _is_purchasable(variant):
        raise VariantNotAvailableError("This product is not currently available.")
    if variant.currency != cart.currency:
        raise CurrencyMismatchError("This product's currency does not match the cart's currency.")

    with transaction.atomic(using="default"):
        item, created = CartItem.objects.select_for_update().get_or_create(
            store=cart.store,
            cart=cart,
            variant=variant,
            defaults={
                "quantity": quantity,
                "unit_price_amount": variant.price_amount,
                "currency": variant.currency,
            },
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=["quantity", "updated_at"])
        recalculate_totals(cart)
    item.refresh_from_db()
    return item


def update_item_quantity(*, cart: Cart, item: CartItem, quantity: int) -> CartItem | None:
    """`quantity <= 0` removes the line entirely (returns None), matching common cart UX."""
    if quantity <= 0:
        remove_item(cart=cart, item=item)
        return None
    with transaction.atomic(using="default"):
        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])
        recalculate_totals(cart)
    return item


def remove_item(*, cart: Cart, item: CartItem) -> None:
    with transaction.atomic(using="default"):
        item.delete()
        recalculate_totals(cart)


def apply_coupon(*, cart: Cart, code: str) -> Cart:
    try:
        coupon = Coupon.objects.get(code=code.strip().upper())
    except Coupon.DoesNotExist as exc:
        raise CouponNotFoundError("No such coupon.") from exc

    validate_coupon(coupon, currency=cart.currency)

    with transaction.atomic(using="default"):
        cart.coupon = coupon
        cart.save(update_fields=["coupon", "updated_at"])
        recalculate_totals(cart)
    return cart


def remove_coupon(*, cart: Cart) -> Cart:
    with transaction.atomic(using="default"):
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])
        recalculate_totals(cart)
    return cart


def reprice_cart(*, cart: Cart) -> Cart:
    """
    The Phase 6 DoD operation: refreshes every line's price snapshot
    from `ProductVariant`'s CURRENT state (catches a merchant price
    change made while the cart sat idle), and drops any line whose
    variant is no longer active -- then recalculates totals. This is
    what a future Checkout (Phase 8) is expected to call before showing
    a final total, per the original spec's "never trust stale
    price/stock -- reverify server-side" requirement.
    """
    with transaction.atomic(using="default"):
        items = (
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .select_related("variant", "variant__product")
        )
        for item in items:
            variant = item.variant
            if not _is_purchasable(variant):
                item.delete()
                continue
            if item.unit_price_amount != variant.price_amount or item.currency != variant.currency:
                item.unit_price_amount = variant.price_amount
                item.currency = variant.currency
                item.save(update_fields=["unit_price_amount", "currency", "updated_at"])
        recalculate_totals(cart)
    cart.refresh_from_db()
    return cart
