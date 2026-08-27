import { defineConfig, devices } from "@playwright/test";

/**
 * docs/ARCHITECTURE.md section 14's named E2E flow: register -> create
 * store -> product -> purchase -> payment -> tracking. Runs against
 * REAL dev servers (dashboard on 3001, storefront on 3000) and the real
 * Django backend on 8000 -- no mocked HTTP layer, matching this
 * project's established "no mocks for the database/backend" testing
 * philosophy (docs/ARCHITECTURE.md section 14's Integration row).
 * `webServer` is intentionally NOT configured here: the three servers
 * (backend + dashboard + storefront) are started separately (see
 * README/CI step), since Playwright's built-in webServer orchestration
 * only manages a single process well and this project already has
 * `.claude/launch.json`/`make up` for that.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  // Explicit, not just implied by fullyParallel:false (which only
  // stops tests WITHIN one file running concurrently -- Playwright
  // still defaults to multiple worker PROCESSES across files). Real
  // failure found adding subscription-checkout-journey.spec.ts: run
  // together with merchant-and-customer-journey.spec.ts on 2 workers,
  // the local Celery worker (solo pool, this project's Windows-
  // compatible dev setup) serialized both specs' background tasks and
  // Phase E's async demo-payment resolution missed its 15s window --
  // not a logic bug (the same spec alone passes reliably in ~7s), a
  // genuine shared-resource contention this suite's specs were never
  // designed to survive running in parallel against each other.
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Needed for staging-smoke.spec.ts (Caddy's internal CA, not a
    // publicly-trusted cert -- see docker-compose.staging.yml). A no-op
    // against the plain-HTTP dev servers the other spec targets.
    ignoreHTTPSErrors: true,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
