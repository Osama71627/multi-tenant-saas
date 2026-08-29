"""
`GET /api/v1/storefront/products`, `/storefront/products/<slug>`,
`/storefront/categories` -- Phase 13. Host-resolved, guest-accessible
(`StorefrontAPIView`), and must never leak draft/archived rows or
merchant-only fields (`cost_price_amount`, product `status`) regardless
of how directly they're requested.
"""

from __future__ import annotations

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


def _login_as(email: str, password: str = "correct-h0rse!") -> APIClient:  # noqa: S107
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


@pytest.fixture
def store_ctx():
    owner = PlatformUser.objects.create_user(
        email="sf-catalog-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    dashboard = _login_as("sf-catalog-owner@example.com")
    store = store_services.create_store(
        owner=owner, name="Storefront Catalog Co", slug="sf-catalog-co"
    )
    hostname = "sf-catalog-co.lvh.me"

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    return {
        "store": store,
        "hostname": hostname,
        "dashboard": dashboard,
        "storefront": HostPinnedClient(),
    }


def _create_product(ctx, *, name, slug, sku, price, status="active"):
    response = ctx["dashboard"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products",
        {"name": name, "slug": slug, "sku": sku, "price_amount": price, "currency": "USD"},
        format="json",
    )
    assert response.status_code == 201, response.data
    product_id = response.data["id"]
    if status != "draft":
        patch = ctx["dashboard"].patch(
            f"/api/v1/dashboard/stores/{ctx['store'].id}/products/{product_id}",
            {"status": status},
            format="json",
        )
        assert patch.status_code == 200, patch.data
    return response.data


def test_product_list_only_returns_active_products(store_ctx):
    _create_product(store_ctx, name="Active Widget", slug="active-widget", sku="W-1", price=1000)
    _create_product(
        store_ctx, name="Draft Widget", slug="draft-widget", sku="W-2", price=1000, status="draft"
    )

    response = store_ctx["storefront"].get("/api/v1/storefront/products")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Active Widget"]


def test_product_list_never_exposes_cost_price(store_ctx):
    _create_product(store_ctx, name="Widget", slug="widget", sku="W-3", price=1000)

    response = store_ctx["storefront"].get("/api/v1/storefront/products")
    body = response.json()
    assert "cost_price_amount" not in body[0]


def test_product_detail_by_slug(store_ctx):
    _create_product(store_ctx, name="Detail Widget", slug="detail-widget", sku="W-4", price=2500)

    response = store_ctx["storefront"].get("/api/v1/storefront/products/detail-widget")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Detail Widget"
    assert body["variants"][0]["price_amount"] == 2500
    assert "cost_price_amount" not in body["variants"][0]
    assert "status" not in body  # merchant-only lifecycle field, not a storefront concern


def test_draft_product_detail_404s(store_ctx):
    _create_product(
        store_ctx, name="Hidden Widget", slug="hidden-widget", sku="W-5", price=1000, status="draft"
    )

    response = store_ctx["storefront"].get("/api/v1/storefront/products/hidden-widget")
    assert response.status_code == 404


def test_nonexistent_slug_404s(store_ctx):
    response = store_ctx["storefront"].get("/api/v1/storefront/products/does-not-exist")
    assert response.status_code == 404


def test_category_filter(store_ctx):
    cat_response = store_ctx["dashboard"].post(
        f"/api/v1/dashboard/stores/{store_ctx['store'].id}/categories",
        {"name": "Gadgets", "slug": "gadgets"},
        format="json",
    )
    assert cat_response.status_code == 201, cat_response.data

    in_category = _create_product(
        store_ctx, name="Gadget One", slug="gadget-one", sku="W-6", price=1000
    )
    _create_product(store_ctx, name="Other Widget", slug="other-widget", sku="W-7", price=1000)

    # No dashboard endpoint attaches a product to a category yet (Phase
    # 12 scope never built one) -- do it directly via the ORM in the
    # store's own tenant context, same pattern as every other test here
    # that needs to set up state with no HTTP surface for it yet.
    from apps.catalog.models import Category, Product, ProductCategory
    from apps.tenancy.context import TenantContext, tenant_context
    from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

    with tenant_context(TenantContext(store_id=store_ctx["store"].id)):
        apply_tenant_context_to_db(store_ctx["store"].id)
        try:
            category = Category.objects.get(slug="gadgets")
            product = Product.objects.get(id=in_category["id"])
            ProductCategory.objects.create(
                store=store_ctx["store"], product=product, category=category
            )
        finally:
            clear_tenant_context_from_db()

    response = store_ctx["storefront"].get("/api/v1/storefront/products?category=gadgets")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Gadget One"]


def test_product_with_all_variants_archived_is_not_browsable(store_ctx):
    product = _create_product(
        store_ctx,
        name="Archived Variant Widget",
        slug="archived-variant-widget",
        sku="W-8",
        price=1000,
    )
    variant_id = product["variants"][0]["id"]

    # No dashboard endpoint changes a variant's status yet (only DELETE
    # exists, which would raise LastVariantError on a single-variant
    # product) -- same direct-ORM pattern as `test_category_filter` for
    # state this phase has no HTTP surface for.
    from apps.catalog.models import ProductVariant
    from apps.tenancy.context import TenantContext, tenant_context
    from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

    with tenant_context(TenantContext(store_id=store_ctx["store"].id)):
        apply_tenant_context_to_db(store_ctx["store"].id)
        try:
            ProductVariant.objects.filter(id=variant_id).update(status="archived")
        finally:
            clear_tenant_context_from_db()

    list_response = store_ctx["storefront"].get("/api/v1/storefront/products")
    assert list_response.json() == []

    detail_response = store_ctx["storefront"].get(
        "/api/v1/storefront/products/archived-variant-widget"
    )
    assert detail_response.status_code == 404


def test_cross_tenant_product_is_not_visible_by_a_different_hostname(store_ctx):
    _create_product(
        store_ctx, name="Tenant A Widget", slug="tenant-a-widget", sku="W-9", price=1000
    )

    other_owner = PlatformUser.objects.create_user(
        email="sf-catalog-owner-b@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_services.create_store(
        owner=other_owner, name="Storefront Catalog Co B", slug="sf-catalog-co-b"
    )

    class OtherHostClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", "sf-catalog-co-b.lvh.me")
            return super().generic(method, path, *args, **kwargs)

    response = OtherHostClient().get("/api/v1/storefront/products")
    assert response.status_code == 200
    assert response.json() == []

    detail_response = OtherHostClient().get("/api/v1/storefront/products/tenant-a-widget")
    assert detail_response.status_code == 404


def test_sort_by_name_is_the_default(store_ctx):
    _create_product(store_ctx, name="Zebra", slug="zebra", sku="SORT-1", price=1000)
    _create_product(store_ctx, name="Apple", slug="apple", sku="SORT-2", price=2000)

    response = store_ctx["storefront"].get("/api/v1/storefront/products")
    assert [p["name"] for p in response.json()] == ["Apple", "Zebra"]


def test_sort_by_price_ascending_and_descending(store_ctx):
    _create_product(store_ctx, name="Mid", slug="sort-mid", sku="SORT-3", price=2000)
    _create_product(store_ctx, name="Cheap", slug="sort-cheap", sku="SORT-4", price=1000)
    _create_product(store_ctx, name="Pricey", slug="sort-pricey", sku="SORT-5", price=3000)

    asc = store_ctx["storefront"].get("/api/v1/storefront/products?sort=price_asc")
    assert [p["name"] for p in asc.json()] == ["Cheap", "Mid", "Pricey"]

    desc = store_ctx["storefront"].get("/api/v1/storefront/products?sort=price_desc")
    assert [p["name"] for p in desc.json()] == ["Pricey", "Mid", "Cheap"]


def test_sort_by_newest(store_ctx):
    first = _create_product(store_ctx, name="First", slug="sort-first", sku="SORT-6", price=1000)
    second = _create_product(store_ctx, name="Second", slug="sort-second", sku="SORT-7", price=1000)
    assert first["id"] != second["id"]  # sanity: genuinely two different products

    response = store_ctx["storefront"].get("/api/v1/storefront/products?sort=newest")
    assert [p["name"] for p in response.json()] == ["Second", "First"]


def test_unknown_sort_value_falls_back_to_name_not_a_500(store_ctx):
    _create_product(store_ctx, name="Zebra", slug="sort-zebra", sku="SORT-8", price=1000)
    _create_product(store_ctx, name="Apple", slug="sort-apple", sku="SORT-9", price=2000)

    response = store_ctx["storefront"].get("/api/v1/storefront/products?sort=not-a-real-option")
    assert response.status_code == 200
    assert [p["name"] for p in response.json()] == ["Apple", "Zebra"]


def test_categories_list(store_ctx):
    response = store_ctx["dashboard"].post(
        f"/api/v1/dashboard/stores/{store_ctx['store'].id}/categories",
        {"name": "Home", "slug": "home"},
        format="json",
    )
    assert response.status_code == 201, response.data

    list_response = store_ctx["storefront"].get("/api/v1/storefront/categories")
    assert list_response.status_code == 200
    assert [c["slug"] for c in list_response.json()] == ["home"]


def test_categories_never_cross_over_between_stores(store_ctx):
    store_ctx["dashboard"].post(
        f"/api/v1/dashboard/stores/{store_ctx['store'].id}/categories",
        {"name": "Home", "slug": "home"},
        format="json",
    )

    other_owner = PlatformUser.objects.create_user(
        email="sf-catalog-owner-c@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store_services.create_store(
        owner=other_owner, name="Storefront Catalog Co C", slug="sf-catalog-co-c"
    )

    class OtherHostClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", "sf-catalog-co-c.lvh.me")
            return super().generic(method, path, *args, **kwargs)

    response = OtherHostClient().get("/api/v1/storefront/categories")
    assert response.status_code == 200
    assert response.json() == []
