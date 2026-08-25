import { execFileSync } from "node:child_process";

import { expect, test } from "@playwright/test";

/**
 * Phase 19 staging smoke test -- NOT a replacement for
 * merchant-and-customer-journey.spec.ts (that Phase 18 test is approved/
 * locked and keeps validating the app against `next start` builds). This
 * one instead proves the DEPLOYED TOPOLOGY: real Caddy TLS termination,
 * real Host-based routing to three separate containers, and real tenant
 * isolation, by running the same kind of flow through
 * https://*.lvh.me (Caddy's internal CA -- `ignoreHTTPSErrors` below is
 * why, not a shortcut around a real cert).
 *
 * Prerequisite seeding runs inside the actual backend container
 * (`docker exec saas-staging-backend-1 ...`) rather than a local venv --
 * this suite is only meaningful against the running
 * docker-compose.staging.yml stack.
 */

const BACKEND_CONTAINER = process.env.E2E_BACKEND_CONTAINER ?? "saas-staging-backend-1";
const DASHBOARD_URL = process.env.E2E_DASHBOARD_URL ?? "https://dashboard.lvh.me";
const PLATFORM_ADMIN_URL = process.env.E2E_PLATFORM_ADMIN_URL ?? "https://admin.lvh.me";
function storefrontOrigin(storeSlug: string): string {
  return `https://${storeSlug}.lvh.me`;
}

test.use({ ignoreHTTPSErrors: true });

function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    ["exec", BACKEND_CONTAINER, "python", "manage.py", "shell", "-c", script],
    { encoding: "utf-8", stdio: "pipe" }
  );
}

function seedCheckoutPrerequisites(storeSlug: string, productSlug: string): void {
  const script = `
from django.db import transaction
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db
from apps.stores.models import Store
from apps.catalog.models import Product
from apps.inventory.models import StockLocation, StockBalance
from apps.shipping.models import ShippingZone, ShippingMethod, ShippingRate
from apps.payments.models import StoreProviderConfig
from apps.payments import encryption

store = Store.objects.get(slug="${storeSlug}")

with transaction.atomic(using="default"), tenant_context(TenantContext(store_id=store.id)):
    apply_tenant_context_to_db(store.id)

    product = Product.objects.get(store=store, slug="${productSlug}")
    product.status = "active"
    product.save(update_fields=["status"])
    variant = product.variants.get(is_default=True)

    location, _ = StockLocation.objects.get_or_create(store=store, name="Main Warehouse")
    StockBalance.objects.update_or_create(
        store=store, variant=variant, location=location,
        defaults={"quantity_on_hand": 100, "quantity_reserved": 0},
    )

    zone, _ = ShippingZone.objects.get_or_create(store=store, name="Everywhere", defaults={"countries": []})
    method, _ = ShippingMethod.objects.get_or_create(
        store=store, zone=zone, name="Standard",
        defaults={"kind": "flat", "is_active": True},
    )
    ShippingRate.objects.get_or_create(
        store=store, method=method,
        defaults={"price_amount": 1000, "currency": "SAR"},
    )

    StoreProviderConfig.objects.get_or_create(
        store=store, provider_key="manual_cod",
        defaults={
            "mode": "test",
            "is_enabled": True,
            "credentials_encrypted": encryption.encrypt_secret("{}"),
        },
    )
print("SEED_OK")
`.trim();
  djangoShell(script);
}

function storeIdFromSlug(slug: string): string {
  const output = djangoShell(
    `from apps.stores.models import Store; print(Store.objects.get(slug="${slug}").id)`
  );
  const lines = output.trim().split("\n");
  return lines[lines.length - 1].trim();
}

test("staging: merchant registers, sells a product, customer orders it, tenant stays isolated", async ({
  page,
}) => {
  const unique = Date.now();
  const email = `staging-smoke-${unique}@example.com`;
  const password = "correct-h0rse!1";
  const storeName = `Staging Smoke Store ${unique}`;
  const storeSlug = `staging-smoke-${unique}`;
  const productName = "Staging Smoke Product";
  const productSlug = "staging-smoke-product";

  // A second, unrelated store -- proves tenant isolation below, not part
  // of the main purchase flow.
  const otherSlug = `staging-smoke-other-${unique}`;
  const otherName = `Staging Smoke Other ${unique}`;

  await page.goto(`${DASHBOARD_URL}/en/register`);
  await page.getByLabel("Full name").fill("Staging Smoke Merchant");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByRole("heading", { name: "Choose a starting look" })).toBeVisible();
  await page.locator('[role="button"]').first().click();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Tell us about your store" })).toBeVisible();
  await page.getByLabel("Store name").fill(storeName);
  await page.getByLabel("Store address").fill(storeSlug);
  await page.getByRole("button", { name: "Create my store" }).click();
  await expect(page).toHaveURL(/\/stores\/[0-9a-f-]+$/);

  await page.getByRole("link", { name: "Products" }).click();
  await page.getByRole("button", { name: /add product/i }).click();
  await page.getByLabel("Name").fill(productName);
  await page.getByLabel("Slug").fill(productSlug);
  await page.getByLabel("SKU").fill(`SKU-${unique}`);
  await page.getByLabel("Price (minor units)").fill("2500");
  await page.getByRole("button", { name: "Create product" }).click();
  await expect(page.getByText(productName)).toBeVisible();

  seedCheckoutPrerequisites(storeSlug, productSlug);
  // A second store, unrelated to the one under test, purely to prove
  // Host-based tenant isolation later -- created directly, no UI needed.
  djangoShell(
    `from apps.stores.models import Store; Store.objects.create(name="${otherName}", slug="${otherSlug}")`
  );

  const storefrontUrl = storefrontOrigin(storeSlug);
  await page.goto(`${storefrontUrl}/en/products/${productSlug}`);
  await expect(page.getByRole("heading", { name: productName })).toBeVisible();
  await page.getByRole("button", { name: /add to cart/i }).click();
  await expect(page.getByText("Added to cart")).toBeVisible();

  await page.goto(`${storefrontUrl}/en/cart`);
  await expect(page.getByText(`SKU-${unique}`)).toBeVisible();
  await page.getByRole("link", { name: "Checkout" }).click();

  await page.getByLabel(/email/i).fill("staging-customer@example.com");
  await page.getByLabel(/full name/i).fill("Staging Smoke Customer");
  await page.getByLabel(/phone/i).fill("+966500000000");
  await page.getByLabel(/country code/i).fill("SA");
  await page.getByLabel(/city/i).fill("Riyadh");
  await page.getByLabel(/address/i).first().fill("123 Test Street");
  await page.getByRole("button", { name: /continue to shipping/i }).click();

  await page.getByRole("radio", { name: /standard/i }).click();
  await page.getByRole("button", { name: /continue to payment/i }).click();

  await page.getByRole("radio", { name: /cash on delivery/i }).click();
  await page.getByRole("button", { name: /place order/i }).click();
  await expect(page).toHaveURL(/\/checkout\/confirmation/);
  const orderNumberText = (await page.getByText(/^ORD-/).first().textContent())!.trim();
  expect(orderNumberText).toBeTruthy();

  const storeId = storeIdFromSlug(storeSlug);
  await page.goto(`${DASHBOARD_URL}/en/stores/${storeId}/orders`);
  await expect(page.getByText(orderNumberText)).toBeVisible();

  // Tenant isolation: the OTHER store's host must never show this
  // product -- proves Caddy's Host-header passthrough and Django's
  // TenantMiddleware resolve independently per request, not by accident
  // of routing to the same backend container.
  await page.goto(`${storefrontOrigin(otherSlug)}/en/products/${productSlug}`);
  await expect(page.getByText(/not found|404/i).first()).toBeVisible();
});

test("staging: platform staff completes MFA and reaches the platform admin host", async ({
  page,
}) => {
  const unique = Date.now();
  const email = `staging-staff-${unique}@example.com`;
  const password = "correct-h0rse!1";

  const output = djangoShell(`
import pyotp
from django.contrib.auth import get_user_model
from apps.accounts.mfa_services import issue_login_challenge, enroll_start, enroll_confirm

User = get_user_model()
user = User.objects.create_user(email="${email}", password="${password}", is_platform_staff=True)
_, raw_token = issue_login_challenge(user)
_, secret, _ = enroll_start(raw_challenge_token=raw_token)
totp = pyotp.TOTP(secret)
enroll_confirm(raw_challenge_token=raw_token, code=totp.now())
print("MFA_READY")
`);
  expect(output).toContain("MFA_READY");

  await page.goto(`${PLATFORM_ADMIN_URL}/en/login`);
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /log in|sign in/i }).click();

  // Password step never issues a JWT directly (Phase 17, locked) -- a TOTP
  // prompt must appear next.
  await expect(page.getByLabel(/verification code|totp|code/i)).toBeVisible();
});
