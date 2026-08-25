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
loses the entire cache and any queued-but-unexecuted Celery message.

## Production decision (Priority 7, Phase "production readiness conditions"): Redis stays disposable

**Decision: B -- Redis is treated as disposable; tasks are safely
recoverable, not "must survive a restart."** Redis persistence
(RDB/AOF) is deliberately NOT being turned on for production. This is
not an oversight -- it's the correct choice given how this codebase
already handles the failure mode, and turning on persistence would add
real operational complexity (volume management, AOF fsync tuning, restore
procedures) to solve a problem the architecture already solves at a more
reliable layer.

**Why this is safe, concretely:**
- `CELERY_TASK_ACKS_LATE = True` (`config/settings/base.py`) already
  protects against a WORKER crashing mid-task (the message is redelivered).
  What persistence would additionally protect against is Redis itself
  losing the message before any worker ever picked it up.
- The notification pipeline's actual source of truth is Postgres, not
  Redis: a domain event is written to Postgres first
  (`transaction.on_commit` fires the Celery task only after that commit
  succeeds -- see `apps/core/events.py`), and
  `apps.notifications.tasks.recover_unprocessed_domain_events` sweeps
  Postgres for any event that was never marked processed and re-dispatches
  it. A Redis restart that drops an in-flight `process_domain_event`
  message is exactly the scenario this recovery sweep exists for.
- The other scheduled tasks (`reconcile_stuck_payment_intents`,
  `apply_subscription_lifecycle_transitions`) are themselves periodic,
  self-healing reconciliation jobs driven by Celery Beat's wall-clock
  schedule -- losing one Redis-queued firing costs at most one interval's
  delay until Beat's next scheduled run, not permanent loss.

**Failure behavior to expect in production:** a Redis restart during
in-flight processing can delay a notification or reconciliation pass by
up to one recovery-sweep/Beat-interval, never lose it silently. If a
future task is added that does NOT have a durable-state recovery path
behind it, that specific gap should be flagged and fixed at the
application layer (a recovery sweep, or making the effect idempotent and
re-triggerable) -- not papered over by turning on Redis persistence.

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
