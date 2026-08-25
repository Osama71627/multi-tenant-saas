"""
Orchestrates zone matching + rate lookup + the pure calculator
(apps/shipping/calculator.py) into an actual quote list. This is the
only place in apps.shipping that touches the DB.
"""

from __future__ import annotations

from apps.catalog.models import ProductVariant
from apps.shipping.calculator import RateOption, compute_method_price
from apps.shipping.carriers import CarrierProvider, MockCarrier
from apps.shipping.models import ShippingMethod, ShippingRate, ShippingZone
from apps.stores.models import Store

_DEFAULT_CARRIER: CarrierProvider = MockCarrier()


def find_matching_zone(
    *, country_code: str, region: str = "", postal_code: str = ""
) -> ShippingZone | None:
    """
    Zones are already ordered by `priority` (model `Meta.ordering`) --
    the first one whose `matches()` is True wins. A destination belongs
    to exactly one zone, never a merge of several.
    """
    for zone in ShippingZone.objects.filter(is_active=True).prefetch_related("methods__rates"):
        if zone.matches(country_code=country_code, region=region, postal_code=postal_code):
            return zone
    return None


def total_weight_grams(items: list[tuple[ProductVariant, int]]) -> int:
    return sum((variant.weight_grams or 0) * quantity for variant, quantity in items)


def get_quotes_for_destination(
    *,
    store: Store,
    country_code: str,
    region: str = "",
    postal_code: str = "",
    items: list[tuple[ProductVariant, int]],
    subtotal_amount: int,
    carrier: CarrierProvider | None = None,
) -> list[RateOption]:
    zone = find_matching_zone(country_code=country_code, region=region, postal_code=postal_code)
    if zone is None:
        return []

    weight_grams = total_weight_grams(items)
    currency = store.default_currency
    carrier = carrier or _DEFAULT_CARRIER

    quotes: list[RateOption] = []
    for method in ShippingMethod.objects.filter(zone=zone, is_active=True):
        rates = list(ShippingRate.objects.filter(method=method))
        price = compute_method_price(
            method=method,
            rates=rates,
            weight_grams=weight_grams,
            subtotal_amount=subtotal_amount,
            currency=currency,
            carrier=carrier,
            country_code=country_code,
            region=region,
        )
        if price is None:
            continue
        quotes.append(
            RateOption(
                method_id=method.id,
                method_name=method.name,
                kind=method.kind,
                price_amount=price,
                currency=currency,
            )
        )
    return quotes
