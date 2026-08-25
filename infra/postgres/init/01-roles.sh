#!/usr/bin/env bash
# Runs once, automatically, the first time the postgres container
# initializes an empty data directory (docker-entrypoint-initdb.d
# convention). Creates the three roles the whole multi-tenancy model
# depends on -- see docs/ARCHITECTURE.md section 2.3 and
# docs/DECISIONS.md:
#
#   app_migrator      -- owns the schema, runs `manage.py migrate`.
#                         CREATEDB, but NOT a Postgres superuser.
#   app_user          -- what the running application (web + celery)
#                         authenticates as. NOSUPERUSER, NOBYPASSRLS,
#                         NOCREATEDB, NOCREATEROLE -- cannot ever see rows
#                         Row-Level Security policies don't explicitly
#                         grant, no matter what application code does.
#   app_platform_admin -- Phase 14, apps.platform_admin ONLY. BYPASSRLS
#                         (so a single request can genuinely read/write
#                         across tenants), but NOSUPERUSER/NOCREATEDB/
#                         NOCREATEROLE/NOREPLICATION, and this script
#                         grants it NOTHING beyond CONNECT/USAGE -- its
#                         actual table-level privileges are narrow,
#                         explicit GRANTs applied by
#                         apps/platform_admin/apps.py's own post_migrate
#                         hook (mirroring apps/tenancy/privileges.py's
#                         app_user hook), never a blanket "ALL TABLES".
#
# Passwords come from environment variables (with dev-only fallbacks) --
# never hard-coded for a real deployment. In production, override
# APP_MIGRATOR_PASSWORD / APP_USER_PASSWORD / APP_PLATFORM_ADMIN_PASSWORD
# via your secret manager / orchestrator, the same as POSTGRES_PASSWORD
# itself.
set -euo pipefail

APP_MIGRATOR_PASSWORD="${APP_MIGRATOR_PASSWORD:-devpass_migrator}"
APP_USER_PASSWORD="${APP_USER_PASSWORD:-devpass_appuser}"
APP_PLATFORM_ADMIN_PASSWORD="${APP_PLATFORM_ADMIN_PASSWORD:-devpass_platformadmin}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_migrator') THEN
        CREATE ROLE app_migrator LOGIN PASSWORD '${APP_MIGRATOR_PASSWORD}' CREATEDB;
      END IF;
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD '${APP_USER_PASSWORD}'
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
      END IF;
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_platform_admin') THEN
        CREATE ROLE app_platform_admin LOGIN PASSWORD '${APP_PLATFORM_ADMIN_PASSWORD}'
          BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
      END IF;
    END
    \$\$;

    ALTER DATABASE "$POSTGRES_DB" OWNER TO app_migrator;
    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO app_user;
    GRANT USAGE ON SCHEMA public TO app_user;
    ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
    ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO app_user;

    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO app_platform_admin;
    GRANT USAGE ON SCHEMA public TO app_platform_admin;
SQL
