# Secret rotation basics (staging)

All staging secrets live in `.env.staging` (gitignored, never committed --
verify with `gitleaks` per [[project-multi-tenant-saas]]'s established CI
gate before assuming a file is clean).

## DJANGO_SECRET_KEY

Rotating invalidates every existing signed session/token that depends on
it (Django's own signing framework -- password reset tokens, any
`itsdangerous`-style signed cookie). This project's auth is JWT-based
(access/refresh tokens signed via `djangorestframework-simplejwt`, whose
signing key follows `SECRET_KEY` unless configured otherwise) -- rotating
`SECRET_KEY` means every currently-issued access/refresh token stops
validating. Treat this as a forced-logout-everyone event: rotate, redeploy,
expect a wave of 401s and re-logins immediately after.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# update DJANGO_SECRET_KEY in .env.staging, then:
$COMPOSE up -d --force-recreate backend celery-worker celery-sync-worker celery-beat
```

## PAYMENT_ENCRYPTION_KEY / MFA_ENCRYPTION_KEY

**Do not just replace these.** Both encrypt data already at rest
(stored payment provider credentials; TOTP secrets) under the CURRENT key
-- see `apps/payments/encryption.py` / `apps/accounts/encryption.py`.
Swapping the key without re-encrypting existing ciphertext makes every
previously-encrypted row permanently undecryptable.

The `_KEY_VERSION` settings (`PAYMENT_ENCRYPTION_KEY_VERSION`,
`MFA_ENCRYPTION_KEY_VERSION`) exist for exactly this: a real rotation
needs a migration that (1) introduces the new key alongside the old one
under a new version, (2) re-encrypts existing rows to the new version,
(3) only then removes the old key. That re-encryption tooling was **not
built** in Phase 19 -- rotating these two keys today means data loss on
existing rows. Flagged as technical debt; do not rotate them on a
staging/production database with real rows until that tooling exists.

## Database role passwords (`APP_MIGRATOR_PASSWORD` / `APP_USER_PASSWORD` /
## `APP_PLATFORM_ADMIN_PASSWORD` / `POSTGRES_SUPERUSER_PASSWORD`)

```bash
docker exec -e PGPASSWORD=$POSTGRES_SUPERUSER_PASSWORD <postgres-container> \
    psql -h localhost -U postgres -c "ALTER ROLE app_user PASSWORD 'NEW_PASSWORD';"
```
Then update the corresponding value in `.env.staging` AND every service's
`DATABASE_URL`/`MIGRATOR_DATABASE_URL`/`PLATFORM_DATABASE_URL` (they
embed the password directly), and recreate the affected services:
```bash
$COMPOSE up -d --force-recreate backend celery-worker celery-sync-worker celery-beat
```
Rotate one role at a time, confirm `/readyz` and a real login still work,
before rotating the next -- never all four roles in the same window.
