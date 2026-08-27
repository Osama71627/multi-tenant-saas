import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "@playwright/test";

/**
 * docs/ARCHITECTURE.md section 14's named E2E flow, end to end:
 * register -> create store -> product -> purchase -> payment -> tracking.
 *
 * Stock/shipping/payment-provider setup (steps that exist purely as
 * PREREQUISITES for a checkout to succeed, not the flow under test) are
 * seeded directly via the backend's own ORM/management shell rather than
 * clicked through the dashboard's settings pages -- the same "seed data,
 * then test the real flow through the UI" split any E2E suite makes
 * between fixture setup and the behavior actually being verified. Every
 * step a REAL merchant or customer would perform (registering, adding a
 * product, browsing, checking out, paying, viewing the order) goes
 * through the real UI against the real backend -- no mocked HTTP layer
 * anywhere in this file.
 *
 * The merchant account + Store are ALSO now seeded rather than clicked
 * through the UI (post-Phase-D gap fix): the dashboard's onboarding
 * wizard, which used to let this test create a Store with no plan and
 * no payment, has been retired for exactly that reason -- see
 * apps/dashboard's "/[locale]/app" page.tsx docstring. There is
 * currently no UI path from "just registered" to "has a Store" at all
 * (Phase E/F/G -- payment, business info, real store creation -- don't
 * exist yet), so this seed step stands in for that future flow the same
 * way seedCheckoutPrerequisites already stands in for the merchant
 * manually configuring shipping/payments. The merchant still logs in
 * through the real UI afterwards, and every step from "add a product"
 * onward is unchanged and still exercises the real UI end to end.
 */

const DASHBOARD_URL = process.env.E2E_DASHBOARD_URL ?? "http://localhost:4001";
// Storefront tenant resolution is Host-header-based (apps/stores/middleware.py)
// -- a bare localhost origin resolves to no store at all, so every
// storefront URL below must use the store's own `lvh.me` subdomain
// (wildcard-DNS'd to 127.0.0.1, exactly like real local dev).
const STOREFRONT_PORT = process.env.E2E_STOREFRONT_PORT ?? "4000";
function storefrontOrigin(storeSlug: string): string {
  return `http://${storeSlug}.lvh.me:${STOREFRONT_PORT}`;
}
const BACKEND_PYTHON =
  process.env.E2E_BACKEND_PYTHON ??
  path.resolve(__dirname, "../../../backend/.venv/Scripts/python.exe");
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");

// Stands in for the not-yet-built payment -> business-info -> store-
// creation pipeline (Phase E/F/G). See the file-level docstring.
function seedMerchantAndStore(
  email: string,
  password: string,
  storeName: string,
  storeSlug: string
): void {
  const script = `
from apps.accounts.models import PlatformUser
from apps.stores.services import create_store

user = PlatformUser.objects.create_user(email="${email}", password="${password}")
create_store(owner=user, name="${storeName}", slug="${storeSlug}")
print("SEED_OK")
`.trim();

  execFileSync(
    BACKEND_PYTHON,
    ["manage.py", "shell", "-c", script],
    { cwd: BACKEND_DIR, encoding: "utf-8", stdio: "pipe" }
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
    # AddProductDialog (dashboard) has no publish toggle -- every new
    # product starts DRAFT (apps.catalog.models.Product.Status), and the
    # storefront only ever renders ACTIVE ones.
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

  execFileSync(
    BACKEND_PYTHON,
    ["manage.py", "shell", "-c", script],
    { cwd: BACKEND_DIR, encoding: "utf-8", stdio: "pipe" }
  );
}

test("register -> create store -> add product -> purchase -> payment -> tracking", async ({
  page,
}) => {
  const unique = Date.now();
  const email = `e2e-journey-${unique}@example.com`;
  const password = "correct-h0rse!1";
  const storeName = `E2E Journey Store ${unique}`;
  const storeSlug = `e2e-journey-${unique}`;
  const productName = "E2E Journey Product";
  const productSlug = "e2e-journey-product";

  // 1/2. Merchant account + Store: seeded, not clicked through the UI --
  // see the file-level docstring for why.
  seedMerchantAndStore(email, password, storeName, storeSlug);

  // Log in through the real UI as that merchant.
  await page.goto(`${DASHBOARD_URL}/en/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/stores\/[0-9a-f-]+$/);

  // 3. Add a product.
  await page.getByRole("link", { name: "Products" }).click();
  await page.getByRole("button", { name: /add product/i }).click();
  await page.getByLabel("Name").fill(productName);
  await page.getByLabel("Slug").fill(productSlug);
  await page.getByLabel("SKU").fill(`SKU-${unique}`);
  await page.getByLabel("Price (minor units)").fill("2500");
  await page.getByRole("button", { name: "Create product" }).click();
  await expect(page.getByText(productName)).toBeVisible();

  // Prerequisites a checkout genuinely needs (stock, shipping, a payment
  // provider) -- seeded directly, not the behavior under test here.
  seedCheckoutPrerequisites(storeSlug, productSlug);

  // 4/5. Purchase, as a customer, on the real storefront.
  const storefrontUrl = storefrontOrigin(storeSlug);
  await page.goto(`${storefrontUrl}/en/products/${productSlug}`);
  await expect(page.getByRole("heading", { name: productName })).toBeVisible();
  await page.getByRole("button", { name: /add to cart/i }).click();
  // The mutation is async (useAddToCart) -- wait for its own success
  // confirmation, or navigating to /cart races it and finds nothing there.
  await expect(page.getByText("Added to cart")).toBeVisible();

  await page.goto(`${storefrontUrl}/en/cart`);
  await expect(page.getByText(`SKU-${unique}`)).toBeVisible();
  await page.getByRole("link", { name: "Checkout" }).click();

  await page.getByLabel(/email/i).fill("customer@example.com");
  await page.getByLabel(/full name/i).fill("E2E Customer");
  await page.getByLabel(/phone/i).fill("+966500000000");
  await page.getByLabel(/country code/i).fill("SA");
  await page.getByLabel(/city/i).fill("Riyadh");
  await page.getByLabel(/address/i).first().fill("123 Test Street");
  await page.getByRole("button", { name: /continue to shipping/i }).click();

  await page.getByRole("radio", { name: /standard/i }).click();
  await page.getByRole("button", { name: /continue to payment/i }).click();

  // 6. Payment (mock/manual COD provider) and order confirmation.
  await page.getByRole("radio", { name: /cash on delivery/i }).click();
  await page.getByRole("button", { name: /place order/i }).click();
  await expect(page).toHaveURL(/\/checkout\/confirmation/);
  const orderNumberText = await page.getByText(/^ORD-/).first().textContent();
  expect(orderNumberText).toBeTruthy();

  // Order tracking, from the merchant's side.
  const storeId = storeIdFromSlug(storeSlug);
  await page.goto(`${DASHBOARD_URL}/en/stores/${storeId}/orders`);
  await expect(page.getByText(orderNumberText!.trim())).toBeVisible();
});

function storeIdFromSlug(slug: string): string {
  const output = execFileSync(
    BACKEND_PYTHON,
    [
      "manage.py",
      "shell",
      "-c",
      `from apps.stores.models import Store; print(Store.objects.get(slug="${slug}").id)`,
    ],
    { cwd: BACKEND_DIR, encoding: "utf-8", stdio: "pipe" }
  );
  const lines = output.trim().split("\n");
  return lines[lines.length - 1].trim();
}
