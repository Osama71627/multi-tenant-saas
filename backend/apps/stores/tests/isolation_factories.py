"""
Registers apps.stores' TenantOwnedModel subclasses with the generic
isolation test suite (backend/tests/test_tenant_isolation.py). Imported
explicitly (not auto-discovered) by that suite -- see the comment there.

NOT itself a `test_*.py` file on purpose: it has no test functions of its
own, only registrations, and importing it must not depend on pytest
collection order.
"""

from apps.stores.models import StoreDomain
from apps.tenancy.testing import register


@register(StoreDomain, select_is_open=True)
def _make_store_domain(store, suffix: str) -> StoreDomain:
    return StoreDomain.objects.create(store=store, hostname=f"{store.slug}-{suffix}.example.com")
