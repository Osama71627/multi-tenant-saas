#!/usr/bin/env bash
# Cron-safe wrapper around backup.sh -- cron runs with a minimal
# environment (no shell profile, no exported secrets), so this reads
# POSTGRES_SUPERUSER_PASSWORD from the env file itself instead of
# assuming it's already exported, then prunes backups past retention and
# writes a clear success/failure line to the log every run (failure
# visibility -- a silent cron job that stops running is how backups quietly
# stop existing).
#
# Retention: 7 days, kept simple on purpose -- this is the staging/demo
# schedule proving the mechanism works end to end; a real production
# schedule/retention policy is an explicit choice for whoever owns that
# host, made when it's provisioned (see runbooks/backup-restore.md).
#
# Install (crontab -e), for a daily 03:00 run:
#   0 3 * * * /path/to/repo/infra/postgres/scheduled-backup.sh >> /path/to/repo/backups/cron.log 2>&1
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.staging"
RETENTION_DAYS=7

cd "$REPO_ROOT" || { echo "$(date -u +%FT%TZ) FAILED: could not cd to $REPO_ROOT"; exit 1; }

if [ ! -f "$ENV_FILE" ]; then
    echo "$(date -u +%FT%TZ) FAILED: $ENV_FILE not found"
    exit 1
fi

POSTGRES_SUPERUSER_PASSWORD=$(grep -m1 '^POSTGRES_SUPERUSER_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
export POSTGRES_SUPERUSER_PASSWORD

if [ -z "$POSTGRES_SUPERUSER_PASSWORD" ]; then
    echo "$(date -u +%FT%TZ) FAILED: POSTGRES_SUPERUSER_PASSWORD not found in $ENV_FILE"
    exit 1
fi

if bash infra/postgres/backup.sh saas-staging saas_staging; then
    echo "$(date -u +%FT%TZ) OK: backup succeeded"
else
    echo "$(date -u +%FT%TZ) FAILED: backup.sh exited non-zero"
    exit 1
fi

DELETED=$(find backups -name '*.dump' -mtime "+${RETENTION_DAYS}" -print -delete 2>/dev/null | wc -l)
echo "$(date -u +%FT%TZ) OK: pruned ${DELETED} backup(s) older than ${RETENTION_DAYS} days"
