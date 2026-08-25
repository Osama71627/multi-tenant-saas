from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_getting_the_cart_creates_one_and_sets_a_cookie(storefront_client):
    response = storefront_client.get("/api/v1/storefront/cart")
    assert response.status_code == 200
    assert response.data["items"] == []
    assert response.data["total_amount"] == 0
    assert "cart_token" in response.cookies
    cookie = response.cookies["cart_token"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"


def test_cart_persists_across_requests_via_cookie(storefront_client):
    first = storefront_client.get("/api/v1/storefront/cart")
    second = storefront_client.get("/api/v1/storefront/cart")
    assert first.data["id"] == second.data["id"]


def test_add_item_to_cart(variant_in_store, storefront_client):
    response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": variant_in_store["variant_id"], "quantity": 2},
        content_type="application/json",
    )
    assert response.status_code == 201, response.data
    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["quantity"] == 2
    assert response.data["subtotal_amount"] == 4000  # 2 x 2000
    assert response.data["total_amount"] == 4000


def test_adding_the_same_variant_twice_increments_quantity(variant_in_store, storefront_client):
    url = "/api/v1/storefront/cart/items"
    payload = {"variant": variant_in_store["variant_id"], "quantity": 1}
    storefront_client.post(url, payload, content_type="application/json")
    response = storefront_client.post(url, payload, content_type="application/json")
    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["quantity"] == 2


def test_adding_a_draft_products_variant_is_rejected(store_with_hostname, storefront_client):
    ctx = store_with_hostname
    product = (
        ctx["dashboard_client"]
        .post(
            f"/api/v1/dashboard/stores/{ctx['store'].id}/products",
            {
                "name": "Draft Widget",
                "slug": "draft-widget",
                "sku": "DRAFT-001",
                "price_amount": 1000,
            },
            format="json",
        )
        .data
    )  # status defaults to "draft"
    response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": product["variants"][0]["id"], "quantity": 1},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_update_item_quantity(variant_in_store, storefront_client):
    add_response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": variant_in_store["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    item_id = add_response.data["items"][0]["id"]

    response = storefront_client.patch(
        f"/api/v1/storefront/cart/items/{item_id}",
        {"quantity": 5},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.data["items"][0]["quantity"] == 5
    assert response.data["subtotal_amount"] == 10000


def test_setting_quantity_to_zero_removes_the_item(variant_in_store, storefront_client):
    add_response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": variant_in_store["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    item_id = add_response.data["items"][0]["id"]

    response = storefront_client.patch(
        f"/api/v1/storefront/cart/items/{item_id}",
        {"quantity": 0},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.data["items"] == []
    assert response.data["total_amount"] == 0


def test_remove_item(variant_in_store, storefront_client):
    add_response = storefront_client.post(
        "/api/v1/storefront/cart/items",
        {"variant": variant_in_store["variant_id"], "quantity": 1},
        content_type="application/json",
    )
    item_id = add_response.data["items"][0]["id"]

    response = storefront_client.delete(f"/api/v1/storefront/cart/items/{item_id}")
    assert response.status_code == 204

    cart = storefront_client.get("/api/v1/storefront/cart")
    assert cart.data["items"] == []
    assert cart.data["total_amount"] == 0


def test_unknown_host_never_creates_a_cart(storefront_client):
    response = storefront_client.get("/api/v1/storefront/cart", HTTP_HOST="totally-unknown.lvh.me")
    assert response.status_code == 404
