"""
Pure pricing calculations -- no DB writes, no side effects, trivially
unit-testable. `apps.carts.services` is the only caller; it fetches the
relevant `TaxRate`/`Coupon` rows and hands plain values in here.

Single rounding point (docs/ARCHITECTURE.md risk #3: "تقريب في نقطة
واحدة"): `decimal.Decimal` with `ROUND_HALF_UP`, converted to an int
minor-unit amount exactly once, in `calculate_tax`. Every other
computation here is exact integer arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class CartTotals:
    subtotal_amount: int
    discount_amount: int
    tax_amount: int
    total_amount: int


def calculate_discount(
    *, subtotal_amount: int, coupon
) -> int:  # noqa: ANN001 -- apps.pricing.models.Coupon | None
    """Never discounts more than the subtotal itself -- a total can't go negative."""
    if coupon is None:
        return 0
    if coupon.kind == coupon.Kind.PERCENTAGE:
        return (subtotal_amount * coupon.percentage_value) // 100
    return min(coupon.fixed_amount_value, subtotal_amount)


def calculate_tax(
    *, taxable_amount: int, tax_rate
) -> int:  # noqa: ANN001 -- apps.pricing.models.TaxRate | None
    if tax_rate is None or taxable_amount <= 0:
        return 0
    exact = Decimal(taxable_amount) * tax_rate.rate_percent / Decimal(100)
    return int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_totals(
    *, subtotal_amount: int, coupon=None, tax_rate=None
) -> CartTotals:  # noqa: ANN001
    discount_amount = calculate_discount(subtotal_amount=subtotal_amount, coupon=coupon)
    taxable_amount = subtotal_amount - discount_amount
    tax_amount = calculate_tax(taxable_amount=taxable_amount, tax_rate=tax_rate)
    total_amount = taxable_amount + tax_amount
    return CartTotals(
        subtotal_amount=subtotal_amount,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
    )
