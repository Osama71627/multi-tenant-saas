# Health / readiness investigation (staging)

Two distinct endpoints on the backend, deliberately different scopes:

- **`/healthz`** -- liveness only. Does not touch the database or cache.
  Returns 200 as long as the Django process itself is up. A load balancer
  should use this to decide "kill and restart the container", never
  "route traffic here."
- **`/readyz`** -- readiness. Checks the two dependencies a request
  actually needs to succeed safely: a real Postgres query
  (`connections["default"].cursor()`) and a real Redis round-trip
  (`cache.set`/`cache.get`). Returns `{"status": "ok", "checks": {...}}`
  with 200, or `{"status": "unavailable", "checks": {...}}` with 503.
  Deliberately shallow -- booleans only, never a hostname, connection
  string, or exception message, since this endpoint is reachable
  unauthenticated by design (any load balancer needs to hit it without
  credentials).

## Investigating "traffic isn't reaching a container"

1. Is the container even up? `$COMPOSE ps <service>`
2. Is `/healthz` answering directly (bypass Caddy, hit the container's own
   port from inside the network)?
   ```bash
   $COMPOSE exec caddy wget -qO- http://backend:8000/healthz
   ```
3. Is `/readyz` green? If not, which check failed -- database or cache?
   That tells you whether to go read
   [redis-outage.md](redis-outage.md) or check Postgres directly.
4. Is Caddy routing the host correctly?
   ```bash
   $COMPOSE logs caddy | grep <hostname>
   ```
   Confirm the `Host` header Caddy received matches what you expect --
   this is the same header Django's `TenantMiddleware` uses to resolve
   the tenant, so a routing bug here shows up as "wrong store" or "404",
   not a Caddy-level error.

## Do NOT expand `/readyz` into a deep diagnostic endpoint

It intentionally does not check Celery, external providers (Stripe,
email), or return version/build info -- that scope creep turns a
frequently-polled, unauthenticated endpoint into both a performance risk
(load balancers may poll every few seconds) and an information-disclosure
risk. Deeper diagnostics belong behind authenticated tooling
(`manage.py shell`, the platform-admin surface, log aggregation), not a
public health check.
