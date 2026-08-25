"""
Keeps `app_user`'s table/sequence privileges in sync after every
migration, without ever granting it BYPASSRLS, SUPERUSER, or ownership.

Why a post_migrate hook instead of doing this once by hand: every new
table any app adds via a future migration needs these grants applied
too, or the app will get permission-denied errors at the exact moment it
tries to serve traffic. `ALTER DEFAULT PRIVILEGES` makes *future* tables
created by `app_migrator` automatically grant to `app_user`; the
`GRANT ... ON ALL TABLES` statements catch anything that already exists.
All statements are idempotent -- safe to run after every migrate.
"""

from __future__ import annotations

from django.db import connections

_GRANT_STATEMENTS = (
    "GRANT USAGE ON SCHEMA public TO app_user",
    "ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public "
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user",
    "ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public "
    "GRANT USAGE, SELECT ON SEQUENCES TO app_user",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user",
)


def grant_app_user_privileges(sender, **kwargs) -> None:
    if kwargs.get("using") != "migrator":
        return
    connection = connections["migrator"]
    with connection.cursor() as cursor:
        for statement in _GRANT_STATEMENTS:
            cursor.execute(statement)
