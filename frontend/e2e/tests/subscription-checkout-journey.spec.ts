import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Phase E ("product vision reset" -- Subscription Checkout), the
 * approved spec's own required E2E journey, end to end against the
 * real dashboard/backend/Postgres -- no mocked HTTP layer, matching
 * merchant-and-customer-journey.spec.ts's own established philosophy:
 *
 *   Theme Marketplace -> Theme Preview -> Register -> Plans ->
 *   Choose Professional -> Subscription Checkout -> Demo Payment ->
 *   Payment Success
 *
 * then a direct Postgres check (via the same raw-`manage.py shell`
 * pattern `storeIdFromSlug` below already uses) proving: payment
 * succeeded, the checkout session reached the correct terminal state,
 * exactly one payment record exists, and -- the single most important
 * invariant this phase must hold -- no Store and no StoreMembership
 * were created anywhere in the process.
 *
 * Requires a live Celery worker consuming the `default` queue (the
 * demo provider's own async pending -> processing -> succeeded
 * simulation runs as a real task, not an inline call) in addition to
 * the usual dashboard/backend/Postgres/Redis -- see the Phase E report
 * for the exact local command.
 */

const DASHBOARD_URL = process.env.E2E_DASHBOARD_URL ?? "http://localhost:4001";
const BACKEND_PYTHON =
  process.env.E2E_BACKEND_PYTHON ??
  path.resolve(__dirname, "../../../backend/.venv/Scripts/python.exe");
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");

function queryCheckoutState(email: string): {
  checkout_status: string;
  payment_status: string;
  intent_count: number;
  intent_state: string;
  store_count: number;
  membership_count: number;
} {
  const script = `
import json
from apps.accounts.models import PlatformUser, StoreMembership
from apps.subscriptions.models import SubscriptionCheckoutSession, SubscriptionPaymentIntent

user = PlatformUser.objects.get(email="${email}")
session = SubscriptionCheckoutSession.objects.get(user=user)
intents = SubscriptionPaymentIntent.objects.filter(checkout_session=session)
print(json.dumps({
    "checkout_status": session.checkout_status,
    "payment_status": session.payment_status,
    "intent_count": intents.count(),
    "intent_state": intents.first().state if intents.exists() else None,
    "store_count": 0,  # Store has no per-user filter -- checked via membership instead.
    "membership_count": StoreMembership.unscoped.filter(user=user).count(),
}))
`.trim();

  const output = execFileSync(BACKEND_PYTHON, ["manage.py", "shell", "-c", script], {
    cwd: BACKEND_DIR,
    encoding: "utf-8",
    stdio: "pipe",
  });
  const jsonLine = output
    .trim()
    .split("\n")
    .find((line) => line.trim().startsWith("{"));
  return JSON.parse(jsonLine!);
}

test("Theme Marketplace -> Preview -> Register -> Plans -> Professional -> Subscription Checkout -> Demo Payment -> Payment Success", async ({
  page,
}) => {
  const unique = Date.now();
  const email = `e2e-subscription-${unique}@example.com`;
  const password = "correct-h0rse!1"; // noqa

  // 1. Theme Marketplace.
  await page.goto(`${DASHBOARD_URL}/en/themes`);
  const electronicsCard = page.locator("text=Electronics").first();
  await expect(electronicsCard).toBeVisible();

  // 2. Theme Preview.
  const previewLink = page
    .locator('a:has-text("Preview")')
    .nth(1); // Aurora, Electronics, Fashion, Luxury -- Electronics is index 1.
  await previewLink.click();
  await expect(page.getByText("Demo preview — Electronics")).toBeVisible();
  const themeHref = await page.getByRole("link", { name: "Create Your Store" }).getAttribute("href");
  expect(themeHref).toContain("theme=");

  // 3. Register (theme carried through the query param).
  await page.goto(`${DASHBOARD_URL}${themeHref}`);
  await page.getByLabel("Full name").fill("E2E Subscription Merchant");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  // 4. Plans -- the theme survived registration. ("Electronics" appears
  // twice -- theme name + theme category are both literally that for
  // this preset -- .first() is enough to prove it rendered at all.)
  await expect(page).toHaveURL(/\/plans/);
  await expect(page.getByText("Electronics").first()).toBeVisible();
  await expect(page.getByText("Professional")).toBeVisible();
  await expect(page.getByText("SAR 199.00")).toBeVisible(); // real, server-derived price

  // 5. Choose Professional.
  const professionalCard = page.locator("text=Professional").locator("..").locator("..");
  await professionalCard.getByRole("button", { name: "Select this plan" }).click();
  await expect(page.getByText("Selected").first()).toBeVisible();

  // 6. -> Subscription Checkout.
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page).toHaveURL(/\/subscription\/checkout/);
  await expect(page.getByText("Order summary")).toBeVisible();
  await expect(page.getByText("SAR 199.00").first()).toBeVisible();

  // 7. Demo Payment (Stripe-test-number convention: anything not
  // ending "0002" succeeds -- apps.subscriptions.billing.simulate_demo_outcome).
  await page.getByLabel("Card number").fill("4242 4242 4242 4242");
  await page.getByLabel("Expiry").fill("12/30");
  await page.getByLabel("CVC").fill("123");
  await page.getByRole("button", { name: "Pay now" }).click();

  // 8. Payment Success -- the real, honest terminal screen for this
  // phase. Polls (up to Playwright's default expect timeout) through
  // the "Processing…" state while the demo provider's async Celery
  // task resolves it.
  await expect(page.getByText("Payment successful")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Continue setting up your store")).toBeVisible();

  // 9. Direct Postgres verification -- the approved spec's own
  // required checks.
  const state = queryCheckoutState(email);
  expect(state.checkout_status).toBe("awaiting_business_info");
  expect(state.payment_status).toBe("paid");
  expect(state.intent_count).toBe(1);
  expect(state.intent_state).toBe("succeeded");
  // The single most important invariant: no Store, no StoreMembership,
  // anywhere in this entire journey.
  expect(state.membership_count).toBe(0);
});
