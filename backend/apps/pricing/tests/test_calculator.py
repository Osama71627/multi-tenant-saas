"""Pure unit tests -- no DB needed."""

from __future__ import annotations

from types import SimpleNamespace

from apps.pricing.calculator import calculate_discount, calculate_tax, calculate_totals
from apps.pricing.models import Coupon


def _percentage_coupon(value: int) -> SimpleNamespace:
    return SimpleNamespace(kind=Coupon.Kind.PERCENTAGE, percentage_value=value, Kind=Coupon.Kind)


def _fixed_coupon(value: int) -> SimpleNamespace:
    return SimpleNamespace(
        kind=Coupon.Kind.FIXED_AMOUNT, fixed_amount_value=value, Kind=Coupon.Kind
    )


def _tax_rate(percent: str) -> SimpleNamespace:
    from decimal import Decimal

    return SimpleNamespace(rate_percent=Decimal(percent))


def test_no_coupon_no_discount():
    assert calculate_discount(subtotal_amount=10000, coupon=None) == 0


def test_percentage_discount():
    assert calculate_discount(subtotal_amount=10000, coupon=_percentage_coupon(10)) == 1000


def test_fixed_discount():
    assert calculate_discount(subtotal_amount=10000, coupon=_fixed_coupon(1500)) == 1500


def test_fixed_discount_never_exceeds_subtotal():
    assert calculate_discount(subtotal_amount=1000, coupon=_fixed_coupon(5000)) == 1000


def test_no_tax_rate_no_tax():
    assert calculate_tax(taxable_amount=10000, tax_rate=None) == 0


def test_tax_rounds_half_up_at_the_single_rounding_point():
    # 333 * 15% = 49.95 -> rounds to 50
    assert calculate_tax(taxable_amount=333, tax_rate=_tax_rate("15.00")) == 50


def test_zero_taxable_amount_has_no_tax():
    assert calculate_tax(taxable_amount=0, tax_rate=_tax_rate("15.00")) == 0


def test_full_totals_subtotal_discount_tax_total():
    totals = calculate_totals(
        subtotal_amount=10000, coupon=_percentage_coupon(10), tax_rate=_tax_rate("15.00")
    )
    assert totals.subtotal_amount == 10000
    assert totals.discount_amount == 1000
    # taxable = 9000; tax = 1350
    assert totals.tax_amount == 1350
    assert totals.total_amount == 10350


def test_totals_with_no_coupon_or_tax_rate():
    totals = calculate_totals(subtotal_amount=5000)
    assert totals == calculate_totals(subtotal_amount=5000, coupon=None, tax_rate=None)
    assert totals.total_amount == 5000
