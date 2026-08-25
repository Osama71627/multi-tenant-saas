"""
Explicit Phase 4 requirement: re-verify the empty-GUC RLS behavior
(docs/PHASE_3_REPORT.md section 5) against catalog's own tables, not
just the ones that happened to exist when the bug was found. All 10
catalog tables use the same `standard_tenant_policy_sql` helper, already
fixed -- this proves that fix actually covers them too, rather than
assuming it does.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.catalog.models import Product, ProductVariant
from apps.tenancy.context import get_current_store_id, tenant_context
from apps.tenancy.db import clear_tenant_context_from_db
from apps.tenancy.exceptions import TenantContextMissingError

pytestmark = pytest.mark.django_db


def test_python_level_manager_fails_closed_with_no_context_active():
    """
    `.objects` (TenantManager) must refuse to run at all with no tenant
    context -- this is the FIRST line of defense (apps/tenancy/models.py),
    checked before any SQL is even sent.
    """
    with tenant_context(None):
        assert get_current_store_id() is None
        with pytest.raises(TenantContextMissingError):
            list(Product.objects.all())


def test_unscoped_query_with_cleared_db_context_returns_empty_not_an_error():
    """
    The exact scenario that crashed in Phase 3: GUC explicitly cleared
    to '' (not truly unset), then an RLS-gated query runs anyway (here,
    deliberately, via `.unscoped` to bypass the Python-level guard above
    and exercise PostgreSQL's policy directly).
    """
    clear_tenant_context_from_db()
    assert list(Product.unscoped.all()) == []
    assert list(ProductVariant.unscoped.all()) == []


def test_all_catalog_tables_use_the_null_safe_rls_expression():
    catalog_tables = [
        "catalog_product",
        "catalog_productoption",
        "catalog_productoptionvalue",
        "catalog_productvariant",
        "catalog_variantoptionvalue",
        "catalog_category",
        "catalog_productcategory",
        "catalog_tag",
        "catalog_producttag",
        "catalog_productimage",
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename, qual, with_check FROM pg_policies WHERE tablename = ANY(%s)",
            [catalog_tables],
        )
        rows = cursor.fetchall()

    tables_checked = set()
    for table, qual, with_check in rows:
        for clause in (qual, with_check):
            if clause and "current_setting" in clause:
                tables_checked.add(table)
                assert "nullif" in clause.lower(), f"{table} policy is not null-safe: {clause!r}"

    assert tables_checked == set(catalog_tables), tables_checked
