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
