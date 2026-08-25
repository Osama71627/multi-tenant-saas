"""`ShippingZone.matches()` -- pure logic on an unsaved instance, no DB needed."""

from __future__ import annotations

from apps.shipping.models import ShippingZone


def test_empty_countries_is_a_catch_all():
    zone = ShippingZone(countries=[], regions=[], postal_patterns=[])
    assert zone.matches(country_code="SA") is True
    assert zone.matches(country_code="EG") is True


def test_country_list_restricts_matching():
    zone = ShippingZone(countries=["SA", "AE"], regions=[], postal_patterns=[])
    assert zone.matches(country_code="SA") is True
    assert zone.matches(country_code="EG") is False


def test_region_list_restricts_matching_within_a_matched_country():
    zone = ShippingZone(countries=["SA"], regions=["Riyadh"], postal_patterns=[])
    assert zone.matches(country_code="SA", region="Riyadh") is True
    assert zone.matches(country_code="SA", region="Jeddah") is False


def test_postal_pattern_is_a_prefix_match():
    zone = ShippingZone(countries=[], regions=[], postal_patterns=["11"])
    assert zone.matches(country_code="SA", postal_code="11564") is True
    assert zone.matches(country_code="SA", postal_code="22564") is False


def test_postal_pattern_configured_but_no_postal_code_given_does_not_match():
    zone = ShippingZone(countries=[], regions=[], postal_patterns=["11"])
    assert zone.matches(country_code="SA", postal_code="") is False
