"""
Proves the *precondition* for every other isolation test: the role the
running application actually authenticates as (`app_user`, the `default`
DB alias) structurally cannot bypass Row-Level Security, no matter what
Python code does. If this test ever fails, every other isolation test in
the suite is meaningless -- they'd be trusting a role that could ignore
the policies entirely.
"""

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def test_default_connection_authenticates_as_the_restricted_role():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        (current_user,) = cursor.fetchone()
    assert current_user == "app_user", (
        "The `default` DB alias (used by every plain ORM call) is not "
        "connecting as `app_user`. If this is `app_migrator` or any "
        "superuser/table-owner role, RLS is silently bypassed for all "
        "normal application code."
    )


def test_app_user_cannot_bypass_rls():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = 'app_user'"
        )
        rolsuper, rolbypassrls, rolcreatedb, rolcreaterole = cursor.fetchone()
    assert rolsuper is False, "app_user must not be a PostgreSQL superuser"
    assert rolbypassrls is False, "app_user must not have BYPASSRLS"
    assert rolcreatedb is False, "app_user must not have CREATEDB"
    assert rolcreaterole is False, "app_user must not have CREATEROLE"


def test_app_user_does_not_own_tenant_tables():
    with connection.cursor() as cursor:
        cursor.execute("SELECT tableowner FROM pg_tables WHERE tablename = 'stores_storedomain'")
        (owner,) = cursor.fetchone()
    assert owner != "app_user", (
        "app_user owns stores_storedomain -- table owners bypass RLS by "
        "default in PostgreSQL unless FORCE ROW LEVEL SECURITY is set. "
        "The schema-owning role must be app_migrator, never app_user."
    )


@pytest.mark.parametrize("table_name", ["stores_store", "stores_storedomain"])
def test_rls_is_actually_enabled_on_tenant_tables(table_name):
    with connection.cursor() as cursor:
        cursor.execute("SELECT relrowsecurity FROM pg_class WHERE relname = %s", [table_name])
        (enabled,) = cursor.fetchone()
    assert enabled is True, f"Row-Level Security is not enabled on {table_name}"
