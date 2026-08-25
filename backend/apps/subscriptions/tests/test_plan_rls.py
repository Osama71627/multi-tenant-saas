"""
Required proof for Phase 10, approved architecture decision 1: RLS is
the actual write boundary on the platform-global Plan tables, not just
the ABSENCE of an INSERT/UPDATE/DELETE policy on paper -- and NOT the
PostgreSQL table-level GRANT, which `app_user` genuinely holds (the
post_migrate hook in apps/tenancy/privileges.py grants
SELECT/INSERT/UPDATE/DELETE on ALL TABLES, this one included). If RLS
were somehow disabled or misconfigured, that GRANT alone would let
`app_user` write to Plan -- these tests prove that does NOT happen.

Every assertion here runs on the `default` DB alias, i.e. genuinely AS
`app_user` (see apps/tenancy/tests/test_rls_role_privileges.py, which
proves that alias's identity) -- not `app_migrator`.
"""

from __future__ import annotations

import pytest
from django.db import Error as DjangoDatabaseError
from django.db import connection, transaction

from apps.subscriptions.models import Plan, PlanVersion
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded_plan() -> Plan:
    return Plan.objects.get(is_default_trial=True)


def test_app_user_can_select_plans(seeded_plan):
    assert Plan.objects.filter(id=seeded_plan.id).exists()


def test_app_user_cannot_insert_a_plan():
    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            Plan.objects.create(code="attempted-insert", name="Attempted Insert")


def test_app_user_cannot_update_a_plan(seeded_plan):
    """
    UPDATE/DELETE behave differently from INSERT under PostgreSQL RLS: with
    row security enabled and NO policy applicable to that command, the
    target row is simply invisible to it -- the statement succeeds but
    matches ZERO rows, it does not raise (INSERT raises instead, because a
    row being inserted has nothing to filter against, only a WITH CHECK to
    fail outright). Both are real write-boundary proofs; this one is the
    "0 rows affected" shape, matching
    backend/tests/test_tenant_isolation.py's own UPDATE/DELETE assertions.
    """
    affected = Plan.objects.filter(id=seeded_plan.id).update(name="Renamed")
    assert affected == 0

    seeded_plan.refresh_from_db()
    assert seeded_plan.name == "Free Trial"  # provably untouched


def test_app_user_cannot_delete_a_plan(seeded_plan):
    deleted_count, _ = Plan.objects.filter(id=seeded_plan.id).delete()
    assert deleted_count == 0

    assert Plan.objects.filter(id=seeded_plan.id).exists()


def test_app_user_cannot_insert_a_plan_version(seeded_plan):
    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            PlanVersion.objects.create(
                plan=seeded_plan,
                version_number=999,
                price_monthly=0,
                price_yearly=0,
                currency="SAR",
            )


def test_tenant_context_has_no_effect_on_plan_visibility_or_writes(seeded_plan):
    """Plan is platform-global -- setting a tenant context (or none at
    all) must never change whether it's visible (always) or writable
    (never, for app_user)."""
    with tenant_context(TenantContext(store_id=None)):
        apply_tenant_context_to_db(None)
        try:
            assert Plan.objects.filter(id=seeded_plan.id).exists()
            affected = Plan.objects.filter(id=seeded_plan.id).update(name="Should not work")
            assert affected == 0
        finally:
            clear_tenant_context_from_db()


def test_rls_is_enabled_on_every_plan_table():
    with connection.cursor() as cursor:
        for table_name in (
            "subscriptions_plan",
            "subscriptions_planversion",
            "subscriptions_planversionfeature",
            "subscriptions_planversionquota",
        ):
            cursor.execute("SELECT relrowsecurity FROM pg_class WHERE relname = %s", [table_name])
            (enabled,) = cursor.fetchone()
            assert enabled is True, f"RLS is not enabled on {table_name}"


def test_app_user_has_table_level_write_grants_but_rls_still_blocks(seeded_plan):
    """Explicitly proves the distinction the review round called out: the
    table-level GRANT genuinely exists (this is NOT a 'permission denied
    at the GRANT level' rejection) -- RLS is what's actually stopping the
    write."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT has_table_privilege('app_user', 'subscriptions_plan', 'INSERT')")
        (has_insert_grant,) = cursor.fetchone()
    assert has_insert_grant is True, (
        "This test's premise is broken if app_user has no INSERT grant at "
        "all -- the point is that RLS blocks the write even though the "
        "table-level GRANT is present."
    )

    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            Plan.objects.create(code="grant-vs-rls", name="Grant vs RLS")
