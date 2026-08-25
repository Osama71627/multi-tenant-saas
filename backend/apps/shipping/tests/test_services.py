"""DB-touching orchestration tests -- real PostgreSQL, real RLS-scoped tenant context."""

from __future__ import annotations

import pytest

from apps.catalog.models import Product, ProductVariant
from apps.shipping import services
from apps.shipping.models import ShippingMethod, ShippingRate, ShippingZone
from apps.shipping.tests.conftest import store_db_context

pytestmark = pytest.mark.django_db


def _make_variant(store, *, weight_grams=1000) -> ProductVariant:
    product = Product.objects.create(store=store, name="Widget", slug="widget")
    return ProductVariant.objects.create(
        store=store,
        product=product,
        sku="WIDGET-1",
        currency="SAR",
        price_amount=5000,
        is_default=True,
        option_signature=[],
        weight_grams=weight_grams,
    )


def test_find_matching_zone_respects_priority_order(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        ShippingZone.objects.create(store=store, name="Catch-all", countries=[], priority=10)
        specific = ShippingZone.objects.create(
            store=store, name="Saudi only", countries=["SA"], priority=0
        )

        matched = services.find_matching_zone(country_code="SA")
        assert matched.id == specific.id


def test_find_matching_zone_returns_none_when_nothing_matches(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        ShippingZone.objects.create(store=store, name="Saudi only", countries=["SA"])
        assert services.find_matching_zone(country_code="EG") is None


def test_find_matching_zone_tie_break_on_equal_priority_is_deterministic(owner_client_and_store):
    """`ShippingZone.Meta.ordering = ["priority", "id"]` (models.py) already gives a
    deterministic tie-break: `id` is UUIDv7 -- globally unique, time-sortable, never
    equal between two rows -- so two zones sharing a `priority` never depend on
    PostgreSQL's unspecified row order. Proven here, not just asserted."""
    with store_db_context(store := owner_client_and_store[2]):
        first = ShippingZone.objects.create(store=store, name="First", countries=["SA"], priority=5)
        second = ShippingZone.objects.create(
            store=store, name="Second", countries=["SA"], priority=5
        )
        assert first.id < second.id  # UUIDv7 creation order

        matched_once = services.find_matching_zone(country_code="SA")
        matched_again = services.find_matching_zone(country_code="SA")
        assert matched_once.id == first.id
        assert matched_again.id == first.id


def test_get_quotes_for_destination_combines_flat_and_free_methods(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        variant = _make_variant(store, weight_grams=500)
        zone = ShippingZone.objects.create(store=store, name="KSA", countries=["SA"])
        flat = ShippingMethod.objects.create(
            store=store, zone=zone, name="Flat", kind=ShippingMethod.Kind.FLAT
        )
        ShippingRate.objects.create(store=store, method=flat, price_amount=1500, currency="SAR")
        free = ShippingMethod.objects.create(
            store=store, zone=zone, name="Free", kind=ShippingMethod.Kind.FREE
        )

        quotes = services.get_quotes_for_destination(
            store=store,
            country_code="SA",
            items=[(variant, 2)],
            subtotal_amount=10000,
        )

        by_name = {q.method_name: q for q in quotes}
        assert by_name["Flat"].price_amount == 1500
        assert by_name["Free"].price_amount == 0
        assert {q.method_id for q in quotes} == {flat.id, free.id}


def test_get_quotes_for_destination_omits_methods_with_no_matching_tier(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        variant = _make_variant(store, weight_grams=50000)  # 50kg -- outside every tier below
        zone = ShippingZone.objects.create(store=store, name="KSA", countries=["SA"])
        weight_based = ShippingMethod.objects.create(
            store=store, zone=zone, name="Weight tiered", kind=ShippingMethod.Kind.WEIGHT_BASED
        )
        ShippingRate.objects.create(
            store=store,
            method=weight_based,
            min_value=0,
            max_value=1000,
            price_amount=1000,
            currency="SAR",
        )

        quotes = services.get_quotes_for_destination(
            store=store, country_code="SA", items=[(variant, 1)], subtotal_amount=0
        )

        assert quotes == []


def test_get_quotes_for_destination_no_matching_zone_returns_empty(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        variant = _make_variant(store)
        ShippingZone.objects.create(store=store, name="Egypt only", countries=["EG"])

        quotes = services.get_quotes_for_destination(
            store=store, country_code="SA", items=[(variant, 1)], subtotal_amount=0
        )
        assert quotes == []


def test_get_quotes_for_destination_uses_injected_carrier(owner_client_and_store):
    from apps.shipping.carriers import CarrierProvider, CarrierRateOption

    class _StubCarrier(CarrierProvider):
        def get_rates(self, *, country_code, region, weight_grams, currency):
            return [CarrierRateOption(service_name="Stub", price_amount=999, currency=currency)]

        def create_shipment(self, **kwargs):
            raise NotImplementedError

        def track(self, tracking_number):
            raise NotImplementedError

        def cancel(self, tracking_number):
            raise NotImplementedError

    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        variant = _make_variant(store)
        zone = ShippingZone.objects.create(store=store, name="KSA", countries=["SA"])
        ShippingMethod.objects.create(
            store=store, zone=zone, name="Carrier", kind=ShippingMethod.Kind.CARRIER_CALCULATED
        )

        quotes = services.get_quotes_for_destination(
            store=store,
            country_code="SA",
            items=[(variant, 1)],
            subtotal_amount=0,
            carrier=_StubCarrier(),
        )

        assert len(quotes) == 1
        assert quotes[0].price_amount == 999


def test_total_weight_grams_sums_quantity_weighted():
    variant_a = ProductVariant(weight_grams=200)
    variant_b = ProductVariant(weight_grams=None)  # missing weight treated as 0
    assert services.total_weight_grams([(variant_a, 3), (variant_b, 5)]) == 600
