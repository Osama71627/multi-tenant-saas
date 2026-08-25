from __future__ import annotations

import pytest

from apps.suppliers.models import Supplier
from apps.suppliers.pricing import compute_suggested_price


def test_markup_percent():
    price = compute_suggested_price(
        cost_amount=1000, strategy=Supplier.PricingStrategy.MARKUP_PERCENT, value=50
    )
    assert price == 1500


def test_margin_percent():
    # price such that (price - cost) / price == 20% => price = cost / 0.8
    price = compute_suggested_price(
        cost_amount=800, strategy=Supplier.PricingStrategy.MARGIN_PERCENT, value=20
    )
    assert price == 1000


def test_fixed_price():
    price = compute_suggested_price(
        cost_amount=1000, strategy=Supplier.PricingStrategy.FIXED, value=2500
    )
    assert price == 2500


def test_min_profit_floor_applies():
    # markup of 1% on a 1000 cost would be 1010 (10 profit), but
    # min_profit_amount=500 must win.
    price = compute_suggested_price(
        cost_amount=1000,
        strategy=Supplier.PricingStrategy.MARKUP_PERCENT,
        value=1,
        min_profit_amount=500,
    )
    assert price == 1500


def test_margin_percent_never_divides_by_zero_or_negative():
    # value >= 100 is capped internally rather than raising or going negative.
    price = compute_suggested_price(
        cost_amount=1000, strategy=Supplier.PricingStrategy.MARGIN_PERCENT, value=150
    )
    assert price > 1000


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        compute_suggested_price(cost_amount=1000, strategy="not-a-real-strategy", value=10)
