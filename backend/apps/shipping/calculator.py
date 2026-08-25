"""
Pure shipping-rate calculation -- no DB queries in here, matching
docs/ARCHITECTURE.md section 9 ("محرّك التسعير نقي... قابل للاختبار
بالكامل بلا DB"). Callers (apps/shipping/services.py) fetch the
relevant `ShippingMethod`/`ShippingRate` rows and hand plain data in.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.shipping.carriers import CarrierProvider
from apps.shipping.models import ShippingMethod, ShippingRate


@dataclass(frozen=True, slots=True)
class RateOption:
    method_id: object
    method_name: str
    kind: str
    price_amount: int
    currency: str


def _price_for_tier(rates: list[ShippingRate], value: int) -> int | None:
    for rate in rates:
        lower = rate.min_value if rate.min_value is not None else 0
        upper = rate.max_value
        if value >= lower and (upper is None or value <= upper):
            return rate.price_amount
    return None


def compute_method_price(
    *,
    method: ShippingMethod,
    rates: list[ShippingRate],
    weight_grams: int,
    subtotal_amount: int,
    currency: str,
    carrier: CarrierProvider | None = None,
    country_code: str = "",
    region: str = "",
) -> int | None:
    """`None` means this method genuinely has no valid price for these inputs (e.g. a
    weight-tiered method with no tier covering this weight) -- the method is simply
    omitted from the quote list, never silently priced at 0."""
    if method.kind == ShippingMethod.Kind.FREE:
        return 0
    if method.kind == ShippingMethod.Kind.FLAT:
        return rates[0].price_amount if rates else None
    if method.kind == ShippingMethod.Kind.WEIGHT_BASED:
        return _price_for_tier(rates, weight_grams)
    if method.kind == ShippingMethod.Kind.PRICE_BASED:
        return _price_for_tier(rates, subtotal_amount)
    if method.kind == ShippingMethod.Kind.CARRIER_CALCULATED:
        if carrier is None:
            return None
        options = carrier.get_rates(
            country_code=country_code, region=region, weight_grams=weight_grams, currency=currency
        )
        return options[0].price_amount if options else None
    return None  # pragma: no cover - exhaustive over ShippingMethod.Kind
