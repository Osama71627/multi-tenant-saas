# E2E tests

Playwright suite covering docs/ARCHITECTURE.md section 14's named flow:
register → create store → product → purchase → payment → tracking.

## Prerequisites

Three things must already be running, against the same database:

1. The Django backend (`cd backend && python manage.py runserver`), reachable at `http://localhost:8000` by default.
2. The dashboard app in production mode (`pnpm --filter @saas/dashboard build && pnpm --filter @saas/dashboard start`), reachable at `http://localhost:4001` by default.
3. The storefront app in production mode (`pnpm --filter @saas/storefront build && pnpm --filter @saas/storefront start`), reachable at `http://localhost:4000` by default.

`*.lvh.me` (wildcard DNS to 127.0.0.1) is used for the storefront's per-store
subdomain, exactly like local dev already does — no `/etc/hosts` edits
needed.

## Running

```bash
cd frontend/e2e
npx playwright install chromium  # first time only
npx playwright test
```

Override the default ports/URLs with `E2E_DASHBOARD_URL`,
`E2E_STOREFRONT_PORT`, and `E2E_BACKEND_PYTHON` (path to the backend's
venv Python, for the small amount of prerequisite fixture seeding this
suite does directly via `manage.py shell` — see the test file's own
docstring for what that is and why).

From the frontend root: `pnpm test:e2e` (deliberately a separate script
from `pnpm test`, which only runs the fast, infra-free Vitest suites).
