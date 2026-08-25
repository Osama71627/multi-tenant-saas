"""Pure unit tests -- no DB needed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.shipping.calculator import compute_method_price
from apps.shipping.carriers import CarrierRateOption, MockCarrier
from apps.shipping.models import ShippingMethod


def _method(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind)


def _rate(min_value=None, max_value=None, price_amount=0) -> SimpleNamespace:
    return SimpleNamespace(min_value=min_value, max_value=max_value, price_amount=price_amount)


def test_free_shipping_is_always_zero_even_with_rates_present():
    price = compute_method_price(
        method=_method(ShippingMethod.Kind.FREE),
        rates=[_rate(price_amount=999)],
        weight_grams=5000,
        subtotal_amount=10000,
        currency="SAR",
    )
    assert price == 0


def test_flat_rate_uses_the_only_rate():
    price = compute_method_price(
        method=_method(ShippingMethod.Kind.FLAT),
        rates=[_rate(price_amount=1200)],
        weight_grams=100,
        subtotal_amount=5000,
        currency="SAR",
    )
    assert price == 1200


def test_flat_rate_with_no_rate_configured_is_none():
    price = compute_method_price(
        method=_method(ShippingMethod.Kind.FLAT),
        rates=[],
        weight_grams=100,
        subtotal_amount=5000,
        currency="SAR",
    )
    assert price is None


def test_weight_based_picks_matching_tier():
    rates = [_rate(0, 999, 500), _rate(1000, None, 1500)]
    assert (
        compute_method_price(
            method=_method(ShippingMethod.Kind.WEIGHT_BASED),
            rates=rates,
            weight_grams=500,
            subtotal_amount=0,
            currency="SAR",
        )
        == 500
    )
    assert (
        compute_method_price(
            method=_method(ShippingMethod.Kind.WEIGHT_BASED),
            rates=rates,
            weight_grams=5000,
            subtotal_amount=0,
            currency="SAR",
        )
        == 1500
    )


def test_weight_based_outside_every_tier_is_none():
    rates = [_rate(0, 999, 500)]
    price = compute_method_price(
        method=_method(ShippingMethod.Kind.WEIGHT_BASED),
        rates=rates,
        weight_grams=5000,
        subtotal_amount=0,
        currency="SAR",
    )
    assert price is None


def test_price_based_picks_matching_tier():
    rates = [_rate(0, 4999, 1000), _rate(5000, None, 0)]
    assert (
        compute_method_price(
            method=_method(ShippingMethod.Kind.PRICE_BASED),
            rates=rates,
            weight_grams=0,
            subtotal_amount=5000,
            currency="SAR",
        )
        == 0
    )


def test_carrier_calculated_uses_carrier_provider():
    class _StubCarrier:
        def get_rates(self, *, country_code, region, weight_grams, currency):
            return [CarrierRateOption(service_name="Stub", price_amount=777, currency=currency)]

    price = compute_method_price(
        method=_method(ShippingMethod.Kind.CARRIER_CALCULATED),
        rates=[],
        weight_grams=100,
        subtotal_amount=0,
        currency="SAR",
        carrier=_StubCarrier(),
        country_code="SA",
    )
    assert price == 777


def test_carrier_calculated_without_a_carrier_is_none():
    price = compute_method_price(
        method=_method(ShippingMethod.Kind.CARRIER_CALCULATED),
        rates=[],
        weight_grams=100,
        subtotal_amount=0,
        currency="SAR",
        carrier=None,
    )
    assert price is None


def test_mock_carrier_is_deterministic_and_weight_tiered():
    carrier = MockCarrier()
    light = carrier.get_rates(country_code="SA", region="", weight_grams=500, currency="SAR")
    heavy = carrier.get_rates(country_code="SA", region="", weight_grams=2500, currency="SAR")
    assert light[0].price_amount == 1500 + 300  # base + 1 tier (ceil(0.5kg) = 1kg)
    assert heavy[0].price_amount == 1500 + 3 * 300  # ceil(2.5kg) = 3kg
    assert light == carrier.get_rates(
        country_code="SA", region="", weight_grams=500, currency="SAR"
    )


def test_mock_carrier_fulfillment_methods_are_explicitly_unimplemented():
    """Real implementations land with apps.orders (Phase 8+) -- see carriers.py's docstring.
    Asserting `NotImplementedError` (not just leaving it uncovered) keeps that contract explicit."""
    carrier = MockCarrier()
    with pytest.raises(NotImplementedError):
        carrier.create_shipment()
    with pytest.raises(NotImplementedError):
        carrier.track("TRACK-123")
    with pytest.raises(NotImplementedError):
        carrier.cancel("TRACK-123")
