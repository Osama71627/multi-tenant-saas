"""Registers apps.pricing TenantOwnedModels with the generic isolation test suite."""

from apps.pricing.models import Coupon, TaxRate
from apps.tenancy.testing import register


@register(TaxRate)
def _tax_rate_factory(store, suffix: str) -> TaxRate:
    return TaxRate.objects.create(
        store=store, name=f"VAT {suffix}", country_code="SA", rate_percent="15.00", is_active=False
    )


@register(Coupon)
def _coupon_factory(store, suffix: str) -> Coupon:
    return Coupon.objects.create(
        store=store,
        code=f"CODE-{suffix}".upper(),
        kind=Coupon.Kind.PERCENTAGE,
        percentage_value=10,
    )
