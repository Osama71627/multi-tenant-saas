"""
Phase 16 DoD: "a complete mock import works" -- end to end, sync ->
stage -> promote -> real Product/Variant + real stock movement (never a
direct balance write, see apps/suppliers/services.py's module
docstring). Plus the standard tenant-isolation proof every surface in
this project carries.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.inventory.models import StockBalance, StockLocation
from apps.stores import services as store_services
from apps.suppliers.models import Supplier, SupplierProduct
from apps.suppliers.services import (
    AlreadyImportedError,
    promote_supplier_product,
    sync_supplier_catalog,
)
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


def _owner_client_and_store(email: str, slug: str):
    user = PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    store = store_services.create_store(owner=user, name=slug, slug=slug)
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login", {"email": email, "password": "correct-h0rse!"}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client, store


def _in_context(store, fn):
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return fn()
        finally:
            clear_tenant_context_from_db()


def _make_supplier(client, store, *, name="Demo", pricing_value=50) -> Supplier:
    response = client.post(
        f"/api/v1/dashboard/stores/{store.id}/suppliers",
        {"name": name, "pricing_strategy": "markup_percent", "pricing_value": pricing_value},
        format="json",
    )
    assert response.status_code == 201, response.data
    return _in_context(store, lambda: Supplier.objects.get(id=response.data["id"]))


def test_sync_stages_mock_catalog_via_http():
    client, store = _owner_client_and_store("suppliers1@example.com", "suppliers-store-1")
    supplier = _make_supplier(client, store)

    sync_response = client.post(f"/api/v1/dashboard/stores/{store.id}/suppliers/{supplier.id}/sync")
    assert sync_response.status_code == 200
    assert len(sync_response.data) == 5  # MockSupplier's fixed catalog size
    assert all(row["status"] == "staged" for row in sync_response.data)
    assert all(row["suggested_price_amount"] > row["cost_amount"] for row in sync_response.data)


def test_sync_is_idempotent():
    client, store = _owner_client_and_store("suppliers2@example.com", "suppliers-store-2")
    supplier = _make_supplier(client, store)

    _in_context(store, lambda: sync_supplier_catalog(store=store, supplier=supplier))
    _in_context(store, lambda: sync_supplier_catalog(store=store, supplier=supplier))

    count = _in_context(store, lambda: SupplierProduct.objects.filter(supplier=supplier).count())
    assert count == 5


def test_promote_creates_real_product_and_stock_via_inventory_service():
    client, store = _owner_client_and_store("suppliers3@example.com", "suppliers-store-3")
    supplier = _make_supplier(client, store)

    def _run():
        staged = sync_supplier_catalog(store=store, supplier=supplier)
        supplier_product = staged[0]
        location = StockLocation.objects.create(store=store, name="Main")

        product = promote_supplier_product(
            store=store,
            supplier_product=supplier_product,
            name=supplier_product.name,
            slug="promoted-item",
            sku="PROMO-1",
            price_amount=9999,
            location=location,
            initial_stock=42,
        )

        variant = product.variants.get(is_default=True)
        assert variant.price_amount == 9999
        assert variant.cost_price_amount == supplier_product.cost_amount

        balance = StockBalance.objects.get(variant=variant, location=location)
        # Proves the REAL inventory service ran, not a bypass.
        assert balance.quantity_on_hand == 42

        supplier_product.refresh_from_db()
        assert supplier_product.status == SupplierProduct.Status.IMPORTED
        assert supplier_product.imported_variant_id == variant.id

    _in_context(store, _run)


def test_promote_without_location_skips_stock_but_still_creates_product():
    client, store = _owner_client_and_store("suppliers4@example.com", "suppliers-store-4")
    supplier = _make_supplier(client, store)

    def _run():
        staged = sync_supplier_catalog(store=store, supplier=supplier)
        supplier_product = staged[0]

        product = promote_supplier_product(
            store=store,
            supplier_product=supplier_product,
            name=supplier_product.name,
            slug="promoted-item-no-stock",
            sku="PROMO-2",
            price_amount=9999,
        )

        assert product.variants.get(is_default=True).sku == "PROMO-2"
        assert StockBalance.objects.filter(variant__product=product).count() == 0

    _in_context(store, _run)


def test_cannot_promote_the_same_supplier_product_twice():
    client, store = _owner_client_and_store("suppliers5@example.com", "suppliers-store-5")
    supplier = _make_supplier(client, store)

    def _run():
        staged = sync_supplier_catalog(store=store, supplier=supplier)
        supplier_product = staged[0]

        promote_supplier_product(
            store=store,
            supplier_product=supplier_product,
            name=supplier_product.name,
            slug="promoted-once",
            sku="PROMO-3",
            price_amount=9999,
        )

        with pytest.raises(AlreadyImportedError):
            promote_supplier_product(
                store=store,
                supplier_product=supplier_product,
                name=supplier_product.name,
                slug="promoted-twice",
                sku="PROMO-4",
                price_amount=9999,
            )

    _in_context(store, _run)


def test_promote_via_http():
    client, store = _owner_client_and_store("suppliers6@example.com", "suppliers-store-6")
    supplier = _make_supplier(client, store)
    supplier_product = _in_context(
        store, lambda: sync_supplier_catalog(store=store, supplier=supplier)[0]
    )

    response = client.post(
        f"/api/v1/dashboard/stores/{store.id}/supplier-products/{supplier_product.id}/promote",
        {"name": "HTTP Promoted", "slug": "http-promoted", "sku": "HTTP-1", "price_amount": 5000},
        format="json",
    )
    assert response.status_code == 201
    assert "product_id" in response.data


def test_store_a_suppliers_never_visible_to_store_b():
    client_a, store_a = _owner_client_and_store("suppliers7a@example.com", "suppliers-store-7a")
    client_b, store_b = _owner_client_and_store("suppliers7b@example.com", "suppliers-store-7b")
    _make_supplier(client_a, store_a, name="Store A Supplier")
    _make_supplier(client_b, store_b, name="Store B Supplier")

    response = client_a.get(f"/api/v1/dashboard/stores/{store_a.id}/suppliers")
    assert response.status_code == 200
    names = {row["name"] for row in response.data}
    assert names == {"Store A Supplier"}


def test_suppliers_endpoint_requires_membership():
    _client_a, store_a = _owner_client_and_store("suppliers8a@example.com", "suppliers-store-8a")
    client_b, _store_b = _owner_client_and_store("suppliers8b@example.com", "suppliers-store-8b")

    response = client_b.get(f"/api/v1/dashboard/stores/{store_a.id}/suppliers")
    assert response.status_code == 403
