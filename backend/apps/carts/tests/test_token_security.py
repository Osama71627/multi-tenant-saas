"""
Explicit Phase 6 security requirements for the cart token: random and
unguessable, never derivable from `cart.id`/`store_id`, hashed at rest
(never the raw secret), and never treated as an authentication
credential. See apps/carts/models.py and apps/carts/services.py.
"""

from __future__ import annotations

import pytest

from apps.carts.models import Cart
from apps.carts.tests.conftest import store_db_context

pytestmark = pytest.mark.django_db


def test_stored_token_hash_is_a_sha256_hex_digest_not_the_raw_token(
    store_with_hostname, storefront_client
):
    response = storefront_client.get("/api/v1/storefront/cart")
    raw_token = response.cookies["cart_token"].value
    cart_id = response.data["id"]

    with store_db_context(store_with_hostname["store"]):
        cart = Cart.objects.get(id=cart_id)

    assert cart.token_hash != raw_token
    assert len(cart.token_hash) == 64  # sha256 hex digest
    assert all(c in "0123456789abcdef" for c in cart.token_hash)


def test_raw_token_has_real_entropy(storefront_client):
    response = storefront_client.get("/api/v1/storefront/cart")
    raw_token = response.cookies["cart_token"].value
    # secrets.token_urlsafe(32) -- 32 bytes of entropy, base64url-encoded
    # (~43 chars, no padding). Not a strict spec, just a sanity floor
    # against an accidental regression to something short/predictable.
    assert len(raw_token) >= 32


def test_cart_token_is_not_derivable_from_cart_id_or_store_id(
    store_with_hostname, storefront_client
):
    response = storefront_client.get("/api/v1/storefront/cart")
    raw_token = response.cookies["cart_token"].value
    cart_id = response.data["id"]
    store_id = str(store_with_hostname["store"].id)

    assert str(cart_id) not in raw_token
    assert store_id not in raw_token


def test_cart_response_body_never_includes_the_token(storefront_client):
    response = storefront_client.get("/api/v1/storefront/cart")
    assert "token" not in response.data
    assert "token_hash" not in response.data


def test_platform_jwt_is_not_accepted_as_cart_identity(store_with_hostname):
    """
    A merchant's own platform-realm access token must not grant, imply,
    or substitute for a cart -- carts are guest/session-token-based,
    fully independent of `apps.accounts`' JWT realm.
    """
    from django.test import Client
    from rest_framework.test import APIClient

    ctx = store_with_hostname
    # A genuinely VALID platform access token for this store's own owner
    # -- not garbage. A malformed/garbage Authorization header is
    # correctly rejected (401) by PlatformJWTAuthentication regardless
    # of AllowAny (DRF authenticates first, then checks permissions);
    # that's expected, unrelated behavior, not what's under test here.
    login = APIClient().post(
        "/api/v1/auth/login",
        {"email": "cart-store-owner@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    access_token = login.data["access"]

    client = Client()
    response = client.get(
        "/api/v1/storefront/cart",
        HTTP_HOST=ctx["hostname"],
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    # A valid platform JWT is accepted as authentication (no 401), but it
    # grants no special cart access -- a brand new, empty guest cart is
    # created exactly as if no Authorization header had been sent at all.
    assert response.status_code == 200
    assert response.data["items"] == []
