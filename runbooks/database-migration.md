# Database migration (staging)

Migrations run automatically on deploy via the `migrate` one-shot service
(docker-compose.staging.yml) -- `backend`/`celery-*` refuse to start
until it exits 0. This runbook covers doing it manually / diagnosing a
failure.

## Run manually

```bash
$COMPOSE run --rm migrate python manage.py migrate --database=migrator
```

`--database=migrator` is not optional -- the `default` connection in
staging authenticates as `app_user`, which deliberately has no DDL
privileges (see [[project-phase14-platform-admin]]'s locked role
boundaries). Only `app_migrator` can run migrations.

## Check what would run, without applying

```bash
$COMPOSE run --rm migrate python manage.py migrate --database=migrator --plan
```

## A migration fails partway through

Django wraps each migration in a transaction by default (unless it
explicitly opts out with `atomic = False`, e.g. for a `CREATE INDEX
CONCURRENTLY`). For an atomic migration, a failure rolls back cleanly --
re-run after fixing the cause. For a non-atomic one, check
`django_migrations` for what's actually recorded as applied:

```bash
$COMPOSE exec postgres psql -U app_migrator -d saas_staging \
    -c "SELECT app, name, applied FROM django_migrations ORDER BY applied DESC LIMIT 20;"
```

## Reversing a migration

```bash
$COMPOSE run --rm migrate python manage.py migrate <app_label> <previous_migration_name> --database=migrator
```

Only safe for migrations Django can actually reverse (no destructive
`RunPython` without a `reverse_code`, no dropped column with data
already written to it in production). If in doubt, do NOT reverse against
a database with real merchant data -- write a new forward migration
instead.
