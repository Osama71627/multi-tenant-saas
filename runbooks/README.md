# Runbooks

Phase 19 staging operations. Executable, not theoretical -- every command
here was run for real against the actual `docker-compose.staging.yml`
stack during Phase 19 verification. All commands assume:

```bash
cd multi-tenant-Saas
export $(grep -v '^#' .env.staging | xargs)   # loads secrets into the shell
PROJECT="saas-staging"
COMPOSE="docker compose -f docker-compose.staging.yml -p $PROJECT --env-file .env.staging"
```

## Index

- [deploy.md](deploy.md) -- bring the staging stack up from a clean checkout.
- [rollback.md](rollback.md) -- revert to a previous image/commit.
- [database-migration.md](database-migration.md) -- run/undo a Django migration.
- [backup-restore.md](backup-restore.md) -- backup procedure, restore procedure, validation, PITR boundary.
- [celery-failure.md](celery-failure.md) -- worker down, task stuck, queue backing up.
- [redis-outage.md](redis-outage.md) -- broker/cache unavailable.
- [secret-rotation.md](secret-rotation.md) -- rotating DJANGO_SECRET_KEY / encryption keys / DB passwords.
- [failed-deployment.md](failed-deployment.md) -- a deploy that didn't come up healthy.
- [health-investigation.md](health-investigation.md) -- reading /healthz, /readyz, and container health signals.

## Custom domains -- the explicit Phase 19 boundary

Wildcard/subdomain staging routing and TLS genuinely work here (Caddy's
internal CA, `*.lvh.me` -> 127.0.0.1). A real merchant-supplied custom
domain would additionally need: a public ACME issuer reachable from the
edge proxy (Let's Encrypt HTTP-01 or DNS-01), a DNS provider API
integration for on-demand certificate issuance per domain, and a
verification step (TXT/CNAME) proving the merchant controls the domain
before routing traffic to their store. None of that was built in Phase
19 -- it needs a real DNS/hosting provider decision that doesn't exist in
this environment, not just more Caddyfile.
