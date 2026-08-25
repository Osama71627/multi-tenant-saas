"""
End-to-end proof that a real cart's totals reflect apps.pricing's
TaxRate/Coupon through the real storefront HTTP surface -- not just the
calculator's own unit tests.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_cart_totals_include_active_tax_rate(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/tax-rates",
        {"name": "VAT", "country_code": "SA", "rate_percent": "15.00"},
        format="json",
    )

    response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    assert response.data["subtotal_amount"] == 2000
    assert response.data["tax_amount"] == 300  # 15% of 2000
    assert response.data["total_amount"] == 2300


def test_apply_percentage_coupon(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "SAVE10", "kind": "percentage", "percentage_value": 10},
        format="json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )

    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "save10"}, content_type="application/json"
    )
    assert response.status_code == 200, response.data
    assert response.data["coupon_code"] == "SAVE10"
    assert response.data["discount_amount"] == 200  # 10% of 2000
    assert response.data["total_amount"] == 1800


def test_apply_coupon_and_tax_together(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/tax-rates",
        {"name": "VAT", "country_code": "SA", "rate_percent": "15.00"},
        format="json",
    )
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "SAVE10", "kind": "percentage", "percentage_value": 10},
        format="json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "SAVE10"}, content_type="application/json"
    )
    # subtotal 2000, discount 200 -> taxable 1800, tax 15% = 270, total 2070
    assert response.data["subtotal_amount"] == 2000
    assert response.data["discount_amount"] == 200
    assert response.data["tax_amount"] == 270
    assert response.data["total_amount"] == 2070


def test_remove_coupon(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "SAVE10", "kind": "percentage", "percentage_value": 10},
        format="json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "SAVE10"}, content_type="application/json"
    )

    response = storefront_client.delete("/api/v1/storefront/cart/coupon")
    assert response.status_code == 200
    assert response.data["coupon_code"] is None
    assert response.data["discount_amount"] == 0
    assert response.data["total_amount"] == 2000


def test_applying_a_nonexistent_coupon_code_is_rejected(variant_in_store, storefront_client):
    ctx = variant_in_store
    storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": ctx["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "NOPE"}, content_type="application/json"
    )
    assert response.status_code == 400


def test_applying_an_inactive_coupon_is_rejected(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "OLDCODE", "kind": "percentage", "percentage_value": 10, "is_active": False},
        format="json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "OLDCODE"}, content_type="application/json"
    )
    assert response.status_code == 400


def test_fixed_amount_coupon_with_mismatched_currency_is_rejected(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {
            "code": "USDOFF",
            "kind": "fixed_amount",
            "fixed_amount_value": 500,
            "currency": "USD",
        },
        format="json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "USDOFF"}, content_type="application/json"
    )
    assert response.status_code == 400


def test_coupon_not_yet_started_is_rejected(variant_in_store, storefront_client):
    from datetime import timedelta

    from django.utils import timezone

    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {
            "code": "FUTURE10",
            "kind": "percentage",
            "percentage_value": 10,
            "starts_at": (timezone.now() + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "FUTURE10"}, content_type="application/json"
    )
    assert response.status_code == 400


def test_expired_coupon_is_rejected(variant_in_store, storefront_client):
    from datetime import timedelta

    from django.utils import timezone

    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {
            "code": "EXPIRED10",
            "kind": "percentage",
            "percentage_value": 10,
            "ends_at": (timezone.now() - timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "EXPIRED10"}, content_type="application/json"
    )
    assert response.status_code == 400


def test_coupon_at_its_usage_limit_is_rejected(variant_in_store, storefront_client):
    ctx = variant_in_store
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/pricing/coupons",
        {"code": "MAXEDOUT", "kind": "percentage", "percentage_value": 10, "usage_limit": 1},
        format="json",
    )
    from apps.carts.tests.conftest import store_db_context
    from apps.pricing.models import Coupon

    with store_db_context(ctx["store"]):
        Coupon.objects.filter(code="MAXEDOUT").update(times_used=1)

    response = storefront_client.post(
        "/api/v1/storefront/cart/coupon", {"code": "MAXEDOUT"}, content_type="application/json"
    )
    assert response.status_code == 400
