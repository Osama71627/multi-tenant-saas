"""
Cross-tenant regression tests for CheckoutSession + checkout/complete
(approved Phase 8 decision 14). `CheckoutSession` is resolved purely
through `self.cart` (itself resolved from the cart-token cookie, already
proven cross-tenant-safe in Phase 6 -- apps/carts/tests/test_cart_isolation.py),
so a stolen/forged token presented at the wrong store's host can never
reach another store's checkout state -- proven here through the real
storefront HTTP surface, not just the generic isolation suite.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_stores_with_hosts(store_with_hostname):
    from apps.accounts.models import PlatformUser

    store_a = store_with_hostname["store"]
    host_a = store_with_hostname["hostname"]

    owner_b = PlatformUser.objects.create_user(
        email="checkout-iso-owner-b@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_b = store_services.create_store(
        owner=owner_b, name="Checkout Iso B", slug="checkout-iso-b"
    )
    host_b = "checkout-iso-b.lvh.me"

    return {"store_a": store_a, "host_a": host_a, "store_b": store_b, "host_b": host_b}


def test_store_bs_cart_token_at_store_as_host_cannot_start_store_bs_checkout(
    two_stores_with_hosts,
):
    ctx = two_stores_with_hosts
    client = Client()

    client.get("/api/v1/storefront/cart", HTTP_HOST=ctx["host_b"])  # mints a store-B token
    assert "cart_token" in client.cookies

    # Presented at store A's host: `get_or_create_cart` (proven Phase 6) mints a
    # FRESH store-A cart instead of leaking store B's -- so checkout/start operates
    # on that fresh, empty cart, never store B's.
    response = client.post("/api/v1/storefront/checkout/start", HTTP_HOST=ctx["host_a"])
    assert response.status_code == 400  # the fresh store-A cart is empty


def test_checkout_complete_with_a_forged_token_never_resolves_a_session(
    two_stores_with_hosts,
):
    client = Client()
    client.cookies["cart_token"] = "a" * 43  # same shape as secrets.token_urlsafe(32)

    response = client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_HOST=two_stores_with_hosts["host_a"],
        HTTP_IDEMPOTENCY_KEY="forged-token-key",
    )
    # A forged token resolves to a brand new, checkout-less cart -- 404, never
    # someone else's session, and never a 500.
    assert response.status_code == 404
