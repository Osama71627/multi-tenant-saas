# Deploy (staging)

1. Ensure `.env.staging` exists with real secrets (`.env.staging.example`
   lists the required keys; generate with `python3 -c "import secrets;
   print(secrets.token_urlsafe(50))"` etc.). Never commit this file.

2. Build every image:
   ```bash
   $COMPOSE build
   ```

3. Bring the stack up. `migrate` runs once and exits 0 before `backend`/
   `celery-*` start (`depends_on: condition: service_completed_successfully`
   in docker-compose.staging.yml) -- there is no separate manual migrate
   step:
   ```bash
   $COMPOSE up -d
   ```

4. Verify every service is up and, where defined, healthy:
   ```bash
   $COMPOSE ps
   ```
   Expect: `postgres`, `redis` healthy; `migrate` exited (0); `backend`,
   `celery-worker`, `celery-sync-worker`, `celery-beat`, `storefront`,
   `dashboard`, `platform-admin`, `caddy`, `mailhog` running.

5. Smoke-test through the real edge proxy (add `--resolve` or rely on
   `*.lvh.me` DNS; `-k` accepts Caddy's internal CA cert, which is not in
   your system trust store):
   ```bash
   curl -sk https://dashboard.lvh.me/ -o /dev/null -w '%{http_code}\n'
   curl -sk https://admin.lvh.me/ -o /dev/null -w '%{http_code}\n'
   curl -sk https://demo-store.lvh.me/ -o /dev/null -w '%{http_code}\n'
   curl -sk https://demo-store.lvh.me:8443/healthz
   curl -sk https://demo-store.lvh.me:8443/readyz
   ```

6. Tail logs for anything unexpected in the first few minutes:
   ```bash
   $COMPOSE logs -f backend celery-worker celery-beat caddy
   ```

If step 3 fails because `migrate` exits non-zero, do not force backend to
start anyway -- see [failed-deployment.md](failed-deployment.md).
