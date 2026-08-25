"""
Reusable PostgreSQL Row-Level Security policy SQL for the common case:
a table with a `store_id` column that should be fully isolated per
tenant across SELECT/INSERT/UPDATE/DELETE alike.

Usage from a migration (Phase 4+ apps -- catalog, orders, etc. -- all
follow this shape)::

    from django.db import migrations
    from apps.tenancy.rls import standard_tenant_policy_sql

    class Migration(migrations.Migration):
        operations = [
            ...,
            migrations.RunSQL(*standard_tenant_policy_sql("catalog_product")),
        ]

`Store` (the tenant root, keyed by `id` not `store_id`) and `StoreDomain`
(needs an open SELECT policy so hostnames are resolvable before a tenant
is known) are deliberately hand-written instead of using this helper --
see apps/stores/migrations/0001_initial.py.

`NULLIF(..., '')` matters, not decoration: `apps.tenancy.db` clears the
tenant context by setting the GUC to `''` (empty string), not by leaving
it truly unset -- see that module's docstring on why (transaction-scoped
`set_config`, safe under pgbouncer/persistent connections). Casting a
bare `current_setting(...)` straight to `::uuid` raises a hard Postgres
error on `''` (`invalid input syntax for type uuid: ""`) instead of
evaluating to NULL/no-match -- discovered via a real failing test in
Phase 3 (`current_setting('x', true)::uuid` with the GUC set to ''), not
theoretical. `NULLIF(value, '')` turns the empty string into a real NULL
first, so the cast -- and every RLS-gated query issued with no tenant
context active -- fails CLOSED (matches zero rows) instead of erroring.
"""

from __future__ import annotations

_GUC = "app.current_store_id"


def _current_store_id_uuid_expr() -> str:
    return f"NULLIF(current_setting('{_GUC}', true), '')::uuid"


def standard_tenant_policy_sql(table_name: str) -> tuple[str, str]:
    """Returns (forward_sql, reverse_sql) for `migrations.RunSQL`."""
    policy_name = f"{table_name}_tenant_isolation"
    guc_expr = _current_store_id_uuid_expr()
    forward = (
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;\n"
        f"CREATE POLICY {policy_name} ON {table_name}\n"
        f"    USING (store_id = {guc_expr})\n"
        f"    WITH CHECK (store_id = {guc_expr});"
    )
    reverse = (
        f"DROP POLICY IF EXISTS {policy_name} ON {table_name};\n"
        f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;"
    )
    return forward, reverse


def platform_admin_only_policy_sql(table_name: str) -> tuple[str, str]:
    """
    Returns (forward_sql, reverse_sql) for a Phase 14 `apps.platform_admin`
    table (currently just `AuditLog`): RLS is enabled with ZERO policies
    for any command, SELECT included -- unlike `global_readonly_policy_sql`,
    which deliberately keeps an open SELECT. `app_user` therefore cannot
    read or write a single row here no matter what table-level GRANT it
    holds (the same "RLS enabled + no matching policy = deny" mechanism
    documented on `global_readonly_policy_sql`), and neither can
    `app_migrator` at request-serving time since it's never a runtime
    role. Only `app_platform_admin` (BYPASSRLS -- see
    infra/postgres/init/01-roles.sh) can touch this table at all, and
    then only for the specific commands apps/platform_admin/apps.py
    explicitly GRANTs it (SELECT + INSERT, never UPDATE/DELETE -- audit
    logs are append-only, see apps/platform_admin/models.py).
    """
    policy_name = f"{table_name}_platform_admin_only"
    forward = (
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;\n"
        f"-- {policy_name}: intentionally zero CREATE POLICY statements --\n"
        f"-- no role without BYPASSRLS may access this table under any command."
    )
    reverse = f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;"
    return forward, reverse


def global_readonly_policy_sql(table_name: str) -> tuple[str, str]:
    """
    Returns (forward_sql, reverse_sql) for a platform-global table (no
    `store_id` at all -- e.g. `apps.subscriptions.Plan`/`PlanVersion`):
    RLS is enabled, but the only policy defined is an open `SELECT` for
    every role. No INSERT/UPDATE/DELETE policy exists for `app_user`, and
    PostgreSQL denies any command on an RLS-enabled table that has no
    matching policy for that command -- so this is a real write boundary,
    not a formality, even though `app_user` also holds a blanket
    table-level GRANT for all four verbs (see
    apps/tenancy/privileges.py): table-level GRANTs and row-level policies
    are independent checks, and RLS is the one that actually denies here.
    Writes remain possible only through `app_migrator` (schema owner,
    bypasses RLS as table owner) via migrations/fixtures/admin -- never
    through ordinary application request/task traffic. See
    apps/subscriptions/migrations/0001_initial.py and
    apps/subscriptions/tests/test_plan_rls.py (Phase 10, approved
    architecture decision 1: "تحقق صراحة من GRANTs الفعلية... لا تعتمد
    فقط على غياب write policy").
    """
    policy_name = f"{table_name}_select_open"
    forward = (
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;\n"
        f"CREATE POLICY {policy_name} ON {table_name}\n"
        f"    FOR SELECT USING (true);"
    )
    reverse = (
        f"DROP POLICY IF EXISTS {policy_name} ON {table_name};\n"
        f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;"
    )
    return forward, reverse
