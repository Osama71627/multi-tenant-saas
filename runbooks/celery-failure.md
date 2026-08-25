# Celery worker failure (staging)

Three worker processes exist -- `celery-worker` (`default,webhooks,email`),
`celery-sync-worker` (`sync`, concurrency 2, isolated so a slow supplier
integration can't starve order/webhook processing), and `celery-beat`
(the scheduler, not a worker -- it only enqueues, never executes).

## A worker container is down / crash-looping

```bash
$COMPOSE ps celery-worker celery-sync-worker celery-beat
$COMPOSE logs --tail=200 celery-worker
```

Common causes, in order of likelihood: Redis unreachable (see
[redis-outage.md](redis-outage.md)), a missing/invalid env var making
Django settings fail at import time (check the same env the `backend`
service gets -- both load the `&backend_env` anchor in
docker-compose.staging.yml), or an unhandled exception in a task that
Celery's own crash isn't actually causing (workers surviving individual
task failures is expected -- a crash-looping *container* is a startup
problem, not a task problem).

Restart in isolation to see the real startup error without log noise from
other services:
```bash
$COMPOSE up --no-deps --force-recreate celery-worker
```

## Tasks are enqueued but never executing (queue backing up)

Check Celery actually sees the queues it's supposed to consume:
```bash
$COMPOSE exec celery-worker celery -A config inspect active_queues
```
Compare against the `-Q` flags in docker-compose.staging.yml. A task
routed to a queue no running worker consumes will sit forever -- this is
a routing/`-Q` mismatch, not a broker problem.

## Celery Beat's schedule didn't fire

```bash
$COMPOSE logs celery-beat | grep -i scheduler
```
Beat writes its own `celerybeat-schedule` state file inside the
container's ephemeral filesystem in this compose file (no volume mounted
for it) -- a container restart resets that state, which is fine for
staging (it just recomputes next-run times), but means Beat's own crash
history does not persist across restarts. If a scheduled task should have
fired and didn't, check Beat's logs from the CURRENT container instance
only.

## Proving the pipeline works end to end

Phase 19's own proof used a real event, not a synthetic one -- registering
a merchant through the dashboard fires a domain event that
`apps.notifications.tasks.process_domain_event` picks up:
```bash
$COMPOSE logs celery-worker | grep process_domain_event
# [...] Task apps.notifications.tasks.process_domain_event[<id>] received
# [...] Task apps.notifications.tasks.process_domain_event[<id>] succeeded in 0.12s: None
```
and the resulting "Verify your email" message actually landing in mailhog
(`http://localhost:8025`) is the real Django -> Redis -> Celery worker ->
SMTP side effect, confirmed end to end.
