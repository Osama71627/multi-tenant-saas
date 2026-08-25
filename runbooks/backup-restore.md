# Backup / restore (staging)

## What this is, and what it explicitly is not

`infra/postgres/backup.sh` takes a **logical** backup (`pg_dump -Fc`) of
the whole `saas_staging` database, run inside the same Postgres container
the data lives in (so the pg_dump/pg_restore version always matches the
server -- no client/server version drift). This is a point-in-time
*snapshot*, taken on demand.

This is **not** PITR (point-in-time recovery). PITR needs continuous WAL
archiving to durable storage plus a `restore_command` wired up on
recovery -- none of that was configured or tested in Phase 19. Do not
represent this as PITR in any status report; `docs/ARCHITECTURE.md`'s
"PITR يومي" line is aspirational, not yet built.

## Backup

```bash
POSTGRES_SUPERUSER_PASSWORD=$POSTGRES_SUPERUSER_PASSWORD infra/postgres/backup.sh saas-staging saas_staging
```

Writes `backups/saas_staging_<UTC timestamp>.dump`.

## Scheduled backups

`infra/postgres/scheduled-backup.sh` is the cron-safe wrapper: it reads
`POSTGRES_SUPERUSER_PASSWORD` from `.env.staging` directly (cron runs
with no shell profile / exported secrets), runs `backup.sh`, prunes
anything in `backups/` older than 7 days, and writes a clear
`OK`/`FAILED` line per run so a stopped schedule is visible in the log,
not silent.

Installed on this host as a real crontab entry (`crontab -l`):
```
0 3 * * * /path/to/repo/infra/postgres/scheduled-backup.sh >> /path/to/repo/backups/cron.log 2>&1
```

This was verified with an actual scheduled firing (not just a manual
run) during the production-readiness audit: a one-time entry was added a
few minutes in the future, cron fired it for real, and the resulting
dump was confirmed readable via `pg_restore --list` before the one-time
entry was removed, leaving only the daily 03:00 schedule above.

7-day retention is the staging/demo choice made here to prove the
mechanism end to end -- a real production host's actual retention period
is a decision for whoever provisions that host, not inherited
automatically from this default.

## Restore (into an isolated database -- never over the live one)

```bash
POSTGRES_SUPERUSER_PASSWORD=$POSTGRES_SUPERUSER_PASSWORD \
    infra/postgres/restore.sh backups/saas_staging_<timestamp>.dump saas-staging saas_staging_restore_test
```

This creates `saas_staging_restore_test` fresh (dropping any previous run
of the same name), restores the dump into it, and runs two validation
queries: total public-schema table count, and a row count from
`stores_store`. A non-zero, sane table count and a store count matching
what you expect from the source database is the actual proof the backup
is usable -- an unread `.dump` file sitting in `backups/` is not
verification.

Drop the isolated database when done:
```bash
docker exec -e PGPASSWORD=$POSTGRES_SUPERUSER_PASSWORD <postgres-container> \
    psql -h localhost -U postgres -c "DROP DATABASE saas_staging_restore_test;"
```

## What was actually verified in Phase 19

A real backup was taken against the live staging stack, restored into an
isolated database on the same server, and validated by comparing table
counts and a `stores_store` row count against the source -- see the Phase
19 closure report for the exact numbers from that run.
