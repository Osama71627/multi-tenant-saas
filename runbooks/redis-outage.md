# Redis outage / restart (staging)

Redis serves two roles here: Celery broker/result-backend (DB 0) and
Django's cache, including tenant-domain resolution caching and rate
limiting (DB 1) -- see `CACHES`/`CELERY_BROKER_URL` in
`backend/config/settings/base.py`.

## Redis container down

```bash
$COMPOSE ps redis
$COMPOSE logs --tail=100 redis
```

Restart it:
```bash
$COMPOSE up --no-deps --force-recreate redis
```

Redis in this compose file has **no persistence volume** (default
`redis:7-alpine`, no `--appendonly`/RDB volume configured) -- a restart
loses all queued-but-unexecuted Celery tasks and the entire cache. For
staging this is an accepted tradeoff (cache repopulates from Postgres on
next read, tenant resolution just costs one extra DB hit); it would NOT
be an accepted tradeoff for a production broker holding real in-flight
tasks -- see Phase 19 technical debt.

## Impact while Redis is down

- **New requests**: `/readyz`'s cache check fails -> 503, so a load
  balancer correctly stops routing traffic here (this is exactly what
  readiness probes are for). `/healthz` still returns 200 -- the process
  itself is alive, it just can't safely serve traffic yet.
- **Celery workers**: lose their broker connection, log connection errors,
  and reconnect automatically once Redis is back (Celery's default
  broker-connection-retry behavior) -- no manual restart needed once
  Redis itself is healthy again.
- **In-flight Django requests hitting the cache**: any code path that
  doesn't guard a cache call will raise. Check
  `$COMPOSE logs backend | grep -i redis` for the actual failure surface
  before assuming it's silently degraded.

## After Redis comes back

Confirm workers reconnected without a manual restart:
```bash
$COMPOSE exec celery-worker celery -A config inspect ping
```
And confirm readiness recovers:
```bash
curl -sk https://<any-store>.lvh.me:8443/readyz
```
