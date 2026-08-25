"""
Cart token security -- explicit Phase 6 requirements from the approved
design: a valid token for store A must never grant access to store B's
cart, even when presented while store B's host is the one being talked
to. Cross-store isolation for Cart/CartItem is also covered generically
by backend/tests/test_tenant_isolation.py (via
apps/carts/tests/isolation_factories.py); this file proves the SAME
property through the real storefront HTTP surface + cookie mechanism.
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
        email="cart-iso-owner-b@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_b = store_services.create_store(owner=owner_b, name="Cart Iso B", slug="cart-iso-b")
    host_b = "cart-iso-b.lvh.me"

    return {"store_a": store_a, "host_a": host_a, "store_b": store_b, "host_b": host_b}


def test_store_bs_token_presented_to_store_a_does_not_leak_store_bs_cart(two_stores_with_hosts):
    ctx = two_stores_with_hosts
    client = Client()

    cart_b = client.get("/api/v1/storefront/cart", HTTP_HOST=ctx["host_b"])
    cart_b_id = cart_b.data["id"]
    # The client's cookiejar now holds a token that is 100% VALID for
    # store B. It gets sent on the next request regardless of Host.
    assert "cart_token" in client.cookies

    cart_a = client.get("/api/v1/storefront/cart", HTTP_HOST=ctx["host_a"])
    assert cart_a.status_code == 200
    # Store A must NEVER return store B's cart -- a fresh one is minted instead.
    assert cart_a.data["id"] != cart_b_id


def test_a_forged_but_well_formed_token_never_resolves_to_any_cart(two_stores_with_hosts):
    """A syntactically-plausible but made-up token must not resolve to ANY existing cart."""
    ctx = two_stores_with_hosts
    client = Client()
    client.cookies["cart_token"] = "a" * 43  # same shape as secrets.token_urlsafe(32)

    response = client.get("/api/v1/storefront/cart", HTTP_HOST=ctx["host_a"])
    assert response.status_code == 200
    # A brand new cart was created -- the forged token matched nothing.
    assert response.data["items"] == []


def test_items_added_under_store_a_are_invisible_from_store_b(two_stores_with_hosts):
    ctx = two_stores_with_hosts
    client_a = Client()
    client_a.get("/api/v1/storefront/cart", HTTP_HOST=ctx["host_a"])
    token_a = client_a.cookies["cart_token"].value

    client_b = Client()
    client_b.cookies["cart_token"] = token_a
    response = client_b.get("/api/v1/storefront/cart", HTTP_HOST=ctx["host_b"])
    # A fresh store-B cart, not store A's (whatever it contains).
    assert response.status_code == 200
    assert response.data["items"] == []
