"""Registers apps.shipping TenantOwnedModels with the generic isolation test suite."""

from apps.shipping.models import ShippingMethod, ShippingRate, ShippingZone
from apps.tenancy.testing import register


def _make_zone(store, suffix: str) -> ShippingZone:
    return ShippingZone.objects.create(store=store, name=f"Zone {suffix}", countries=["SA"])


def _make_method(store, suffix: str) -> ShippingMethod:
    zone = _make_zone(store, suffix)
    return ShippingMethod.objects.create(
        store=store, zone=zone, name=f"Method {suffix}", kind=ShippingMethod.Kind.FLAT
    )


@register(ShippingZone)
def _zone_factory(store, suffix: str) -> ShippingZone:
    return _make_zone(store, suffix)


@register(ShippingMethod)
def _method_factory(store, suffix: str) -> ShippingMethod:
    return _make_method(store, suffix)


@register(ShippingRate)
def _rate_factory(store, suffix: str) -> ShippingRate:
    method = _make_method(store, suffix)
    return ShippingRate.objects.create(
        store=store, method=method, price_amount=1500, currency="SAR"
    )
