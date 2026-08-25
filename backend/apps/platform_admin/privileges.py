"""
Keeps `app_platform_admin`'s table-level privileges in sync after every
migration -- the `apps.tenancy.privileges` counterpart for the Phase 14
platform role, deliberately kept in THIS app (not `apps.tenancy`, which
must stay domain-agnostic -- see the import-linter contract in
pyproject.toml) and deliberately NOT reusing that module's blanket
"ALL TABLES" pattern.

`app_platform_admin` is BYPASSRLS (infra/postgres/init/01-roles.sh), so
it needs no RLS policy to read/write a row -- but Postgres GRANT and RLS
are independent checks (see apps/tenancy/rls.py's
`global_readonly_policy_sql` docstring), and BYPASSRLS does not imply any
GRANT at all. Without an explicit GRANT on a table, `app_platform_admin`
gets a plain permission-denied error trying to touch it -- which is
exactly the least-privilege behavior the approved Phase 14 decision
requires: this list is a complete, auditable enumeration of every table
`apps.platform_admin` can touch, and adding a new one is a deliberate,
reviewable one-line change here, never an accidental side effect of
`ALTER DEFAULT PRIVILEGES ... ON ALL TABLES`.

Only SELECT/INSERT/UPDATE are ever granted -- never DELETE. Nothing in
apps.platform_admin's Phase 14 scope deletes a row (suspend/activate are
UPDATEs; nothing removes a Store, Plan, PlanVersion, Subscription, or
PlatformUser), and `platform_admin_auditlog` gets SELECT + INSERT only,
enforcing real append-only immutability at the grant level, not just in
application code.
"""

from __future__ import annotations

from django.db import connections

# (table_name, privileges) -- kept as an explicit, reviewable list, not a
# loop over every model in some app label.
_TABLE_GRANTS: tuple[tuple[str, str], ...] = (
    ("stores_store", "SELECT, UPDATE"),
    ("subscriptions_plan", "SELECT, INSERT, UPDATE"),
    ("subscriptions_planversion", "SELECT, INSERT, UPDATE"),
    ("subscriptions_planversionfeature", "SELECT, INSERT"),
    ("subscriptions_planversionquota", "SELECT, INSERT"),
    ("subscriptions_subscription", "SELECT, UPDATE"),
    ("accounts_platformuser", "SELECT"),
    ("platform_admin_auditlog", "SELECT, INSERT"),
    # Phase 15 -- SELECT only, for platform-wide order-count/revenue
    # aggregation (apps.platform_admin.services.overview_metrics).
    # Deliberately just Order (status + total_amount snapshot), never
    # apps.payments -- no card/provider data, and revenue is read from
    # the same total_amount the merchant/customer already see on the
    # order itself, not a second financial ledger.
    ("orders_order", "SELECT"),
    # Phase 17 -- MFA reset (apps.platform_admin.services.reset_user_mfa).
    # UPDATE only, no DELETE, same "never DELETE" posture as every other
    # grant here: a reset revokes a device (blanks confirmed_at, rotates
    # the secret) and invalidates unused recovery codes (marks used_at)
    # rather than removing rows -- an UPDATE, not a DELETE.
    ("accounts_mfatotpdevice", "SELECT, UPDATE"),
    ("accounts_mfarecoverycode", "SELECT, UPDATE"),
)


def grant_platform_admin_privileges(sender, **kwargs) -> None:
    if kwargs.get("using") != "migrator":
        return
    connection = connections["migrator"]
    with connection.cursor() as cursor:
        cursor.execute("GRANT USAGE ON SCHEMA public TO app_platform_admin")
        for table_name, privileges in _TABLE_GRANTS:
            cursor.execute(f"GRANT {privileges} ON {table_name} TO app_platform_admin")
