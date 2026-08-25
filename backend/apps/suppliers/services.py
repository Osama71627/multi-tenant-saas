"""
The two-stage import Phase 16's DoD is about: `sync_supplier_catalog`
(stage) then `promote_supplier_product` (explicit merchant approval ->
real catalog). Neither function ever writes a stock balance directly --
`promote_supplier_product` calls `apps.inventory.services.adjust_stock`
for that, the same service every other stock-affecting flow in this
project goes through (docs/PHASE_5_REPORT.md's invariant: inventory
stays the sole operational stock source of truth). `SupplierProduct.
supplier_stock` is never read by this module except to default the
`initial_stock` a caller didn't specify -- it's a suggestion, not
authoritative.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.catalog import services as catalog_services
from apps.catalog.models import Product
from apps.inventory import services as inventory_services
from apps.inventory.models import StockLocation
from apps.stores.models import Store
from apps.suppliers.models import Supplier, SupplierProduct
from apps.suppliers.providers import get_provider


class AlreadyImportedError(Exception):
    pass


def sync_supplier_catalog(*, store: Store, supplier: Supplier) -> list[SupplierProduct]:
    """Idempotent: re-running updates the same staged rows (matched by
    `external_id`) rather than duplicating them -- a MockSupplier sync
    run twice leaves the catalog exactly as it would after one run,
    just with fresher cost/stock snapshots."""
    provider = get_provider(supplier.provider)
    staged: list[SupplierProduct] = []
    with transaction.atomic(using="default"):
        for dto in provider.fetch_catalog():
            product, _created = SupplierProduct.objects.update_or_create(
                store=store,
                supplier=supplier,
                external_id=dto.external_id,
                defaults={
                    "name": dto.name,
                    "cost_amount": dto.cost_amount,
                    "currency": dto.currency,
                    "supplier_stock": dto.stock,
                },
            )
            staged.append(product)
        supplier.last_synced_at = timezone.now()
        supplier.save(update_fields=["last_synced_at", "updated_at"])
    return staged


def promote_supplier_product(
    *,
    store: Store,
    supplier_product: SupplierProduct,
    name: str,
    slug: str,
    sku: str,
    price_amount: int,
    location: StockLocation | None = None,
    initial_stock: int | None = None,
) -> Product:
    if supplier_product.status == SupplierProduct.Status.IMPORTED:
        raise AlreadyImportedError(
            f"SupplierProduct {supplier_product.id} was already imported "
            f"as variant {supplier_product.imported_variant_id}."
        )

    with transaction.atomic(using="default"):
        product = catalog_services.create_product(
            store=store,
            name=name,
            slug=slug,
            sku=sku,
            price_amount=price_amount,
            currency=supplier_product.currency,
            cost_price_amount=supplier_product.cost_amount,
        )
        variant = product.variants.get(is_default=True)

        stock_to_set = (
            initial_stock if initial_stock is not None else supplier_product.supplier_stock
        )
        if location is not None and stock_to_set:
            inventory_services.adjust_stock(
                store=store,
                variant=variant,
                location=location,
                delta=stock_to_set,
                reason="supplier_import",
                reference=f"supplier_product:{supplier_product.id}",
            )

        supplier_product.status = SupplierProduct.Status.IMPORTED
        supplier_product.imported_variant = variant
        supplier_product.save(update_fields=["status", "imported_variant", "updated_at"])

    return product
