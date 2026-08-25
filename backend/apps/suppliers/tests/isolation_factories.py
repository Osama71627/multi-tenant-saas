"""
Registers apps.suppliers' TenantOwnedModels with the generic isolation
test suite (backend/tests/test_tenant_isolation.py). See
apps/stores/tests/isolation_factories.py for the pattern.
"""

from apps.suppliers.models import Supplier, SupplierProduct
from apps.tenancy.testing import register


def _make_supplier(store, suffix: str) -> Supplier:
    return Supplier.objects.create(store=store, name=f"Supplier {suffix}", pricing_value=50)


@register(Supplier)
def _supplier_factory(store, suffix: str) -> Supplier:
    return _make_supplier(store, suffix)


@register(SupplierProduct)
def _supplier_product_factory(store, suffix: str) -> SupplierProduct:
    supplier = _make_supplier(store, suffix)
    return SupplierProduct.objects.create(
        store=store,
        supplier=supplier,
        external_id=f"ext-{suffix}",
        name=f"Supplier Product {suffix}",
        cost_amount=1000,
        currency="SAR",
    )
