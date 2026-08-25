# Failed deployment (staging)

## `migrate` exits non-zero

`backend`/`celery-*` never start (compose's `service_completed_successfully`
condition blocks them) -- this is the fail-safe working as intended, not
a bug to route around.

```bash
$COMPOSE logs migrate
```
Fix the actual migration error (bad migration, unreachable DB, wrong
`MIGRATOR_DATABASE_URL`), then:
```bash
$COMPOSE up -d migrate
$COMPOSE up -d backend celery-worker celery-sync-worker celery-beat
```

## `backend` starts but `/readyz` returns 503

```bash
curl -sk https://<host>:8443/readyz
```
Read the `checks` object in the response -- it names which dependency
(`database` or `cache`) failed, without leaking connection details. Cross
-reference:
```bash
$COMPOSE logs --tail=100 backend
```

## A frontend container (storefront/dashboard/platform-admin) won't start

These are Next.js `output: "standalone"` builds -- almost always either a
missing required env var (dashboard/platform-admin need
`BACKEND_INTERNAL_URL`; storefront needs `NEXT_PUBLIC_BACKEND_PORT`,
though it has a `"8000"` fallback) or the image simply wasn't rebuilt
after a source change:
```bash
$COMPOSE logs --tail=100 storefront
$COMPOSE build storefront && $COMPOSE up -d storefront
```

## Caddy won't issue a cert / a host returns a TLS error

```bash
$COMPOSE logs caddy
```
`tls internal` (Caddy's own local CA) needs its `staging_caddy_data`
volume intact to keep reusing the same CA across restarts -- if the
volume was removed, every existing `-k`-trusting client is unaffected
(you're already bypassing verification with `-k`) but a real browser that
had previously trusted the old CA will show a fresh untrusted-cert
warning. Regenerating the CA is not itself a failure.

## General rule

Never "fix" a failed deployment by loosening a gate that exists on
purpose -- e.g. skipping `migrate`, hardcoding a fallback secret, or
routing around a 503 from `/readyz`. Per the locked testing/deployment
rules from Phases 17-19: find the root cause, fix it, keep the check.
