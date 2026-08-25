"""
Explicit Phase 6 requirement (carried forward from Phase 3-5): verify
the empty-GUC RLS null-safety fix against carts' AND pricing's own
tables, not just the ones that existed when the bug was found.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.carts.models import Cart
from apps.pricing.models import Coupon
from apps.tenancy.context import get_current_store_id, tenant_context
from apps.tenancy.db import clear_tenant_context_from_db
from apps.tenancy.exceptions import TenantContextMissingError

pytestmark = pytest.mark.django_db


def test_python_level_manager_fails_closed_with_no_context_active():
    with tenant_context(None):
        assert get_current_store_id() is None
        with pytest.raises(TenantContextMissingError):
            list(Cart.objects.all())
        with pytest.raises(TenantContextMissingError):
            list(Coupon.objects.all())


def test_unscoped_query_with_cleared_db_context_returns_empty_not_an_error():
    clear_tenant_context_from_db()
    assert list(Cart.unscoped.all()) == []
    assert list(Coupon.unscoped.all()) == []


def test_all_carts_and_pricing_tables_use_the_null_safe_rls_expression():
    tables = [
        "carts_cart",
        "carts_cartitem",
        "pricing_taxrate",
        "pricing_coupon",
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename, qual, with_check FROM pg_policies WHERE tablename = ANY(%s)",
            [tables],
        )
        rows = cursor.fetchall()

    tables_checked = set()
    for table, qual, with_check in rows:
        for clause in (qual, with_check):
            if clause and "current_setting" in clause:
                tables_checked.add(table)
                assert "nullif" in clause.lower(), f"{table} policy is not null-safe: {clause!r}"

    assert tables_checked == set(tables), tables_checked
