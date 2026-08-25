from __future__ import annotations

from django.utils import timezone

from apps.pricing.models import Coupon


class CouponInvalidError(Exception):
    """The coupon exists but isn't usable now (inactive, outside its date window, or exhausted)."""


def validate_coupon(coupon: Coupon, *, currency: str) -> None:
    if not coupon.is_active:
        raise CouponInvalidError("This coupon is not active.")

    now = timezone.now()
    if coupon.starts_at and now < coupon.starts_at:
        raise CouponInvalidError("This coupon is not active yet.")
    if coupon.ends_at and now > coupon.ends_at:
        raise CouponInvalidError("This coupon has expired.")

    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        raise CouponInvalidError("This coupon has reached its usage limit.")

    if coupon.kind == Coupon.Kind.FIXED_AMOUNT and coupon.currency != currency:
        raise CouponInvalidError("This coupon's currency does not match the cart's currency.")
