import { Badge } from "@saas/ui/badge";
import type { AuroraSettings } from "@saas/theme-aurora";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FIXTURE_CATEGORIES, FIXTURE_PRODUCTS } from "@/components/preview/fixture-catalog";
import { PreviewTabs } from "@/components/preview/preview-tabs";
import { getCssVars, getTheme } from "@/components/preview/theme-registry";
import { PREVIEW_FONT_VARIABLES } from "@/lib/preview-fonts";
import { serverFetch } from "@/lib/session";

interface StoreDetail {
  name: string;
}

interface StoreThemeConfig {
  theme_code: string;
  theme_version_number: number;
  settings: AuroraSettings;
}

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

export default async function StorePreviewPage({
  params,
}: {
  params: Promise<{ storeId: string; locale: string }>;
}) {
  const { storeId, locale } = await params;

  const [storeResponse, themeResponse] = await Promise.all([
    serverFetch(`api/v1/dashboard/stores/${storeId}`),
    serverFetch(`api/v1/dashboard/stores/${storeId}/theme`),
  ]);
  if (!storeResponse.ok || !themeResponse.ok) notFound();

  const store: StoreDetail = await storeResponse.json();
  const themeConfig: StoreThemeConfig = await themeResponse.json();
  const theme = getTheme(themeConfig.theme_code);
  const settings = themeConfig.settings;

  const homeSectionRenderers: Record<string, React.ReactNode> = {
    hero: <theme.Hero headline={settings.hero_headline} subheadline={settings.hero_subheadline} />,
    featured_products: (
      <theme.FeaturedProducts
        products={FIXTURE_PRODUCTS}
        productHref={() => "#"}
        viewAllHref={null}
      />
    ),
    categories: <theme.Categories categories={FIXTURE_CATEGORIES} categoryHref={() => "#"} />,
    newsletter: <theme.Newsletter />,
  };

  const homePanel = (
    <div>
      {settings.homepage_sections.map((section) => (
        <div key={section}>{homeSectionRenderers[section]}</div>
      ))}
    </div>
  );

  const catalogPanel = (
    <div className="mx-auto max-w-6xl px-4 py-10">
      {/* Uses the theme's own ProductGrid (Phase B) -- its
          viewport-based breakpoints won't respond to this
          width-constrained panel the same way a real browser viewport
          would, but the grid's actual density/spacing per theme still
          renders correctly, which is what this panel is for. */}
      <theme.ProductGrid products={FIXTURE_PRODUCTS} productHref={() => "#"} />
    </div>
  );

  const exampleProduct = FIXTURE_PRODUCTS[1]; // the one with a compare-at (sale) price
  const productPanel = exampleProduct ? (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold">{exampleProduct.name}</h1>
        <p className="mt-2 flex items-center gap-2 text-xl font-semibold">
          <span style={{ color: "var(--sf-primary)" }}>
            {formatMoney(exampleProduct.price_amount ?? 0, exampleProduct.currency ?? "USD")}
          </span>
          {exampleProduct.compare_at_price_amount ? (
            <span className="text-base text-gray-400 line-through">
              {formatMoney(exampleProduct.compare_at_price_amount, exampleProduct.currency ?? "USD")}
            </span>
          ) : null}
        </p>
      </div>
      <Badge variant="success">In stock</Badge>
      <p className="text-sm text-gray-600">
        This is an example product page using demo data, styled with your store&apos;s colors and
        font.
      </p>
    </div>
  ) : null;

  const cartItems = FIXTURE_PRODUCTS.slice(0, 2);
  const cartSubtotal = cartItems.reduce((sum, p) => sum + (p.price_amount ?? 0), 0);
  const cartPanel = (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-semibold">Your cart</h1>
      <div className="divide-y rounded-lg border">
        {cartItems.map((product) => (
          <div key={product.id} className="flex items-center justify-between p-4">
            <p className="text-sm font-medium">{product.name}</p>
            <p className="text-sm text-gray-500">
              {formatMoney(product.price_amount ?? 0, product.currency ?? "USD")}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-6 flex items-center justify-between border-t pt-4">
        <span className="text-sm text-gray-600">Subtotal</span>
        <span className="text-lg font-semibold">
          {formatMoney(cartSubtotal, cartItems[0]?.currency ?? "USD")}
        </span>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white">
      <div className="flex items-center justify-between border-b bg-gray-50 px-4 py-2">
        <p className="text-sm font-medium text-gray-600">
          Live preview — demo products shown, not your real catalog
        </p>
        <Link
          href={`/${locale}/stores/${storeId}`}
          className="rounded-md border bg-white px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
        >
          Close preview
        </Link>
      </div>
      <div
        className={`flex flex-1 flex-col overflow-hidden ${PREVIEW_FONT_VARIABLES}`}
        style={{ ...getCssVars(themeConfig.theme_code, settings), fontFamily: "var(--font-sans)" }}
      >
        <theme.Header
          storeName={store.name}
          navOrder={settings.nav_order}
          locale={locale}
          homeHref="#"
          disableNav
        />
        <PreviewTabs
          home={homePanel}
          catalog={catalogPanel}
          product={productPanel}
          cart={cartPanel}
        />
        <theme.Footer storeName={store.name} />
      </div>
    </div>
  );
}
