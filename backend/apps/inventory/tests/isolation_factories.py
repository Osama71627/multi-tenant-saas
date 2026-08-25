"""
Registers every apps.inventory TenantOwnedModel with the generic
isolation test suite (backend/tests/test_tenant_isolation.py). See
apps/stores/tests/isolation_factories.py for the pattern.
"""

from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import StockBalance, StockLocation, StockMovement, StockReservation
from apps.tenancy.testing import register


def _make_location(store, suffix: str) -> StockLocation:
    return StockLocation.objects.create(store=store, name=f"Location {suffix}")


def _make_variant(store, suffix: str) -> ProductVariant:
    product = Product.objects.create(
        store=store, name=f"Product {suffix}", slug=f"product-{store.slug}-{suffix}"
    )
    return ProductVariant.objects.create(
        store=store,
        product=product,
        sku=f"SKU-{store.slug}-{suffix}",
        currency="SAR",
        price_amount=1000,
        is_default=True,
        option_signature=[],
    )


@register(StockLocation)
def _location_factory(store, suffix: str) -> StockLocation:
    return _make_location(store, suffix)


@register(StockBalance)
def _balance_factory(store, suffix: str) -> StockBalance:
    return StockBalance.objects.create(
        store=store,
        variant=_make_variant(store, suffix),
        location=_make_location(store, suffix),
        quantity_on_hand=10,
        quantity_reserved=0,
    )


@register(StockMovement)
def _movement_factory(store, suffix: str) -> StockMovement:
    return StockMovement.objects.create(
        store=store,
        variant=_make_variant(store, suffix),
        location=_make_location(store, suffix),
        kind=StockMovement.Kind.ADJUSTMENT,
        delta_on_hand=10,
        delta_reserved=0,
        balance_on_hand_after=10,
        balance_reserved_after=0,
        reason="isolation test seed",
    )


@register(StockReservation)
def _reservation_factory(store, suffix: str) -> StockReservation:
    return StockReservation.objects.create(
        store=store,
        variant=_make_variant(store, suffix),
        location=_make_location(store, suffix),
        quantity=1,
        reference=f"isolation-{suffix}",
    )
