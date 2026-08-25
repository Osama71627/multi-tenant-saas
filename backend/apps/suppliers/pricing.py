"""Pure pricing calculation -- no DB access, easy to unit test in
isolation. Only ever produces a SUGGESTED selling price; the merchant
can still edit it by hand in the promotion request (see
apps/suppliers/services.py:promote_supplier_product), so this is a
convenience default, not an enforced business rule."""

from __future__ import annotations

from apps.suppliers.models import Supplier

_MAX_MARGIN_PERCENT = 95  # a 100%+ margin_percent is mathematically undefined (division by <= 0)


def compute_suggested_price(
    *, cost_amount: int, strategy: str, value: int, min_profit_amount: int = 0
) -> int:
    if strategy == Supplier.PricingStrategy.FIXED:
        price = value
    elif strategy == Supplier.PricingStrategy.MARKUP_PERCENT:
        price = cost_amount + (cost_amount * value) // 100
    elif strategy == Supplier.PricingStrategy.MARGIN_PERCENT:
        capped_value = min(value, _MAX_MARGIN_PERCENT)
        price = int(cost_amount * 100 / (100 - capped_value))
    else:
        raise ValueError(f"Unknown pricing strategy: {strategy!r}")

    if price - cost_amount < min_profit_amount:
        price = cost_amount + min_profit_amount
    return price
