#!/usr/bin/env bash
# Logical backup for the staging Postgres container -- pg_dump custom
# format (-Fc), run via `docker exec` into the SAME container image the
# data lives in, so the pg_dump/pg_restore version always matches the
# server exactly (no local-client-vs-server version drift).
#
# This is deliberately a logical (pg_dump) backup, NOT physical/PITR --
# see docs/ARCHITECTURE.md's aspirational "PITR يومي" line and
# runbooks/backup-restore.md for why WAL archiving is explicitly out of
# scope for Phase 19 (no WAL-archive infra was configured or tested; do
# not claim PITR is operational because this script exists).
#
# Usage: infra/postgres/backup.sh [compose-project] [db-name]
set -euo pipefail

PROJECT="${1:-saas-staging}"
DB="${2:-saas_staging}"

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

mkdir -p backups
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="backups/${DB}_${TS}.dump"

docker exec -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" "$CONTAINER" \
    pg_dump -h localhost -U postgres -Fc -d "$DB" > "$OUT"

echo "Backup written to ${OUT} ($(du -h "$OUT" | cut -f1))"
