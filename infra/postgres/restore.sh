#!/usr/bin/env bash
# Restores a backup.sh dump into a NEW, isolated database on the SAME
# postgres container (never over the live saas_staging database) and
# runs a basic row-count validation query -- a backup that has never
# been restored is not considered verified (Phase 19 requirement).
#
# Usage: infra/postgres/restore.sh <dump-file> [compose-project] [target-db]
set -euo pipefail

DUMP_FILE="${1:?Usage: restore.sh <dump-file> [compose-project] [target-db]}"
PROJECT="${2:-saas-staging}"
TARGET_DB="${3:-saas_staging_restore_test}"

CONTAINER=$(docker ps --filter "label=com.docker.compose.project=${PROJECT}" \
    --filter "label=com.docker.compose.service=postgres" --format '{{.Names}}' | head -n1)

if [ -z "$CONTAINER" ]; then
    echo "No running postgres container found for compose project '${PROJECT}'." >&2
    exit 1
fi

if [ -z "${POSTGRES_SUPERUSER_PASSWORD:-}" ]; then
    echo "POSTGRES_SUPERUSER_PASSWORD must be set in the environment (same value as .env.staging)." >&2
    exit 1
fi

export PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}"

echo "Dropping any previous ${TARGET_DB} ..."
docker exec -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" "$CONTAINER" \
    psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS ${TARGET_DB};"

echo "Creating isolated ${TARGET_DB} (owned by app_migrator, same as the real schema owner) ..."
docker exec -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" "$CONTAINER" \
    psql -h localhost -U postgres -c "CREATE DATABASE ${TARGET_DB} OWNER app_migrator;"

echo "Restoring ${DUMP_FILE} into ${TARGET_DB} ..."
docker exec -i -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" "$CONTAINER" \
    pg_restore -h localhost -U postgres -d "${TARGET_DB}" --no-owner < "$DUMP_FILE"

echo "Validating: table count and a sample row count ..."
docker exec -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" "$CONTAINER" \
    psql -h localhost -U postgres -d "${TARGET_DB}" -c \
    "SELECT count(*) AS table_count FROM information_schema.tables WHERE table_schema = 'public';"

docker exec -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" "$CONTAINER" \
    psql -h localhost -U postgres -d "${TARGET_DB}" -c \
    "SELECT count(*) AS store_count FROM stores_store;"

echo "Restore validated into ${TARGET_DB}. Drop it when done: docker exec -e PGPASSWORD=*** ${CONTAINER} psql -h localhost -U postgres -c 'DROP DATABASE ${TARGET_DB};'"
