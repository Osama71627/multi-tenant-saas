"""
Fixes a real bug found in Phase 3 (docs/PHASE_3_REPORT.md): the RLS
policies from 0001_initial cast `current_setting(...)` straight to
`::uuid`. `apps.tenancy.db` clears the tenant context by setting that GUC
to `''` (empty string, not truly unsetting it -- see that module's
docstring), and PostgreSQL raises `invalid input syntax for type uuid:
""` when casting an empty string, instead of evaluating to NULL/no-match.
Any RLS-gated query issued with no tenant context active (a legitimate,
expected state -- e.g. a `.unscoped` read during a no-tenant request)
would hard-error instead of failing closed.

Fix: wrap with `NULLIF(..., '')` before casting, so an empty GUC becomes
a real NULL and the comparison safely evaluates to no-match. Same fix
applied to `apps.tenancy.rls.standard_tenant_policy_sql` for every future
table using that helper (accounts_storemembership's corresponding fix is
apps/accounts/migrations/0003_null_safe_rls_policy.py).
"""

from django.db import migrations


def _expr() -> str:
    return "NULLIF(current_setting('app.current_store_id', true), '')::uuid"


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DROP POLICY stores_store_write_self ON stores_store;\n"
                "CREATE POLICY stores_store_write_self ON stores_store\n"
                f"    FOR UPDATE USING (id = {_expr()})\n"
                f"    WITH CHECK (id = {_expr()});\n"
                "DROP POLICY stores_store_delete_self ON stores_store;\n"
                "CREATE POLICY stores_store_delete_self ON stores_store\n"
                f"    FOR DELETE USING (id = {_expr()});"
            ),
            reverse_sql=(
                "DROP POLICY stores_store_write_self ON stores_store;\n"
                "CREATE POLICY stores_store_write_self ON stores_store\n"
                "    FOR UPDATE USING (id = current_setting('app.current_store_id', true)::uuid)\n"
                "    WITH CHECK (id = current_setting('app.current_store_id', true)::uuid);\n"
                "DROP POLICY stores_store_delete_self ON stores_store;\n"
                "CREATE POLICY stores_store_delete_self ON stores_store\n"
                "    FOR DELETE USING (id = current_setting('app.current_store_id', true)::uuid);"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DROP POLICY stores_storedomain_write_self ON stores_storedomain;\n"
                "CREATE POLICY stores_storedomain_write_self ON stores_storedomain\n"
                f"    FOR INSERT WITH CHECK (store_id = {_expr()});\n"
                "DROP POLICY stores_storedomain_update_self ON stores_storedomain;\n"
                "CREATE POLICY stores_storedomain_update_self ON stores_storedomain\n"
                f"    FOR UPDATE USING (store_id = {_expr()})\n"
                f"    WITH CHECK (store_id = {_expr()});\n"
                "DROP POLICY stores_storedomain_delete_self ON stores_storedomain;\n"
                "CREATE POLICY stores_storedomain_delete_self ON stores_storedomain\n"
                f"    FOR DELETE USING (store_id = {_expr()});"
            ),
            reverse_sql=(
                "DROP POLICY stores_storedomain_write_self ON stores_storedomain;\n"
                "CREATE POLICY stores_storedomain_write_self ON stores_storedomain\n"
                "    FOR INSERT WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);\n"
                "DROP POLICY stores_storedomain_update_self ON stores_storedomain;\n"
                "CREATE POLICY stores_storedomain_update_self ON stores_storedomain\n"
                "    FOR UPDATE USING (store_id = current_setting('app.current_store_id', true)::uuid)\n"
                "    WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);\n"
                "DROP POLICY stores_storedomain_delete_self ON stores_storedomain;\n"
                "CREATE POLICY stores_storedomain_delete_self ON stores_storedomain\n"
                "    FOR DELETE USING (store_id = current_setting('app.current_store_id', true)::uuid);"
            ),
        ),
    ]
