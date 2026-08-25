"""
Regression test for a real bug found in Phase 3 (see
docs/PHASE_3_REPORT.md and apps/tenancy/rls.py's docstring):
`apps.tenancy.db` clears the tenant context by setting the
`app.current_store_id` GUC to `''` (empty string), not by truly unsetting
it. Casting that straight to `::uuid` in an RLS policy raises a hard
PostgreSQL error (`invalid input syntax for type uuid: ""`) instead of
evaluating to NULL/no-match -- meaning ANY query against an RLS-protected
table issued with no tenant context active (a normal, expected state,
e.g. `.unscoped` during a no-tenant request) would crash instead of
correctly returning zero rows. Fixed with `NULLIF(value, '')` before the
cast in every policy. This test exists so that fix can never silently
regress.
"""

import pytest
from django.db import connection

from apps.accounts.models import StoreMembership

pytestmark = pytest.mark.django_db


def test_empty_guc_does_not_raise_when_cast_to_uuid():
    """The exact statement PostgreSQL raised on before the fix."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_store_id', '', true)")
        cursor.execute("SELECT NULLIF(current_setting('app.current_store_id', true), '')::uuid")
        (value,) = cursor.fetchone()
    assert value is None


def test_unscoped_query_with_no_tenant_context_returns_empty_not_an_error():
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_store_id', '', true)")
    # No tenant_context() wrapper on purpose -- this simulates exactly the
    # state a connection is left in after TenantMiddleware clears context.
    assert list(StoreMembership.unscoped.all()) == []


def test_rls_policies_use_the_null_safe_expression():
    """
    Direct proof the *deployed* policies were actually updated (not just
    that the helper function that generates new ones was fixed) -- greps
    `pg_policies` for the tables patched by the Phase 3 migrations.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename, policyname, qual, with_check FROM pg_policies "
            "WHERE tablename IN ('stores_store', 'stores_storedomain', 'accounts_storemembership')"
        )
        rows = cursor.fetchall()

    checked_any = False
    for _table, _policy, qual, with_check in rows:
        for clause in (qual, with_check):
            if clause and "current_setting" in clause:
                checked_any = True
                assert (
                    "nullif" in clause.lower()
                ), f"policy clause still casts current_setting() directly: {clause!r}"
    assert checked_any, "expected at least one GUC-comparing policy to check"
