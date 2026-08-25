"""
Same fix as apps/stores/migrations/0002_null_safe_rls_policies.py -- see
that migration's docstring and apps/tenancy/rls.py for the full
explanation. This one covers accounts_storemembership's policy (created
via the now-fixed `standard_tenant_policy_sql` helper in 0002).
"""

from django.db import migrations

from apps.tenancy.rls import standard_tenant_policy_sql

_OLD_POLICY_SQL = (
    "CREATE POLICY accounts_storemembership_tenant_isolation ON accounts_storemembership\n"
    "    USING (store_id = current_setting('app.current_store_id', true)::uuid)\n"
    "    WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);"
)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_passwordresettoken_storemembership"),
        ("stores", "0002_null_safe_rls_policies"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DROP POLICY accounts_storemembership_tenant_isolation "
                "ON accounts_storemembership;\n" + standard_tenant_policy_sql("accounts_storemembership")[0]
            ),
            reverse_sql=(
                "DROP POLICY accounts_storemembership_tenant_isolation "
                "ON accounts_storemembership;\n" + _OLD_POLICY_SQL
            ),
        ),
    ]
