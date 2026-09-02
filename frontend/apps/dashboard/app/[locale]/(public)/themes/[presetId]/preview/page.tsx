import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import type { AuroraSettings } from "@saas/theme-aurora";
import { notFound } from "next/navigation";
import Link from "next/link";

import {
  FIXTURE_CATEGORIES,
  FIXTURE_PRODUCTS,
  HOMESTORE_FIXTURE_CATEGORIES,
  HOMESTORE_FIXTURE_PRODUCTS,
} from "@/components/preview/fixture-catalog";
import { PreviewTabs } from "@/components/preview/preview-tabs";
import { getCssVars, getTheme } from "@/components/preview/theme-registry";
import { getTranslations } from "next-intl/server";
import { PREVIEW_FONT_VARIABLES } from "@/lib/preview-fonts";
import { serverFetch } from "@/lib/session";

interface PublicThemePreset {
  id: string;
  name: string;
  default_settings: AuroraSettings;
  theme_code: string;
  theme_name: string;
  theme_category: string;
}

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

/**
 * Public, unauthenticated theme preview -- Phase B's "I want to see
 * what my store will look like before I buy" requirement. Deliberately
 * reuses the EXACT SAME fixture-based rendering already built and
 * approved for the dashboard's authenticated live-preview
 * (FIXTURE_PRODUCTS/FIXTURE_CATEGORIES, PreviewTabs) rather than the
 * earlier-considered "flagged demo Store" design: this project's own
 * Theme/Template decision already settled that question --
 * `apps/themes/models.py`'s module docstring states outright "No
 * `DemoStore` model exists anywhere in this app, deliberately... live
 * preview is a rendering MODE... never a real tenant/Store row." That
 * decision is followed here, not re-litigated: no tenant, no real
 * Store, no possibility of leaking into or out of any merchant's data,
 * by construction rather than by a permission check.
 */
export default async function PublicThemePreviewPage({
  params,
}: {
  params: Promise<{ locale: string; presetId: string }>;
}) {
  const { locale, presetId } = await params;
  const t = await getTranslations("themesMarketplace");

  const response = await serverFetch(`api/v1/themes/public/presets/${presetId}`);
  if (!response.ok) notFound();
  const preset: PublicThemePreset = await response.json();

  const theme = getTheme(preset.theme_code);
  const settings = preset.default_settings;
  // See apps/dashboard/app/[locale]/(app)/stores/[storeId]/preview/
  // page.tsx's identical comment -- HomeStore ships real bundled demo
  // photography, fixture-only.
  const isHomestore = preset.theme_code === "homestore";
  const fixtureProducts = isHomestore ? HOMESTORE_FIXTURE_PRODUCTS : FIXTURE_PRODUCTS;
  const fixtureCategories = isHomestore ? HOMESTORE_FIXTURE_CATEGORIES : FIXTURE_CATEGORIES;

  const homeSectionRenderers: Record<string, React.ReactNode> = {
    hero: (
      <theme.Hero
        headline={settings.hero_headline}
        subheadline={settings.hero_subheadline}
        shopHref="#"
      />
    ),
    featured_products: (
      <theme.FeaturedProducts products={fixtureProducts} productHref={() => "#"} viewAllHref={null} />
    ),
    categories: <theme.Categories categories={fixtureCategories} categoryHref={() => "#"} />,
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
      <theme.ProductGrid products={fixtureProducts} productHref={() => "#"} />
    </div>
  );

  const exampleProduct = fixtureProducts[1];
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
        This is an example product page using demo data -- not a real store.
      </p>
    </div>
  ) : null;

  const cartItems = fixtureProducts.slice(0, 2);
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
    <div className="flex min-h-screen flex-col bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-gray-50 px-4 py-2">
        <p className="text-sm font-medium text-gray-600">
          {t("demoNotice", { theme: preset.theme_name })}
        </p>
        <div className="flex items-center gap-2">
          <Link
            href={`/${locale}/themes`}
            className="rounded-md border bg-white px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
          >
            {t("backToMarketplace")}
          </Link>
          <Button asChild size="sm">
            {/* The preset id, not the theme code -- see the marketplace
                card's identical link for why. */}
            <Link href={`/${locale}/register?theme=${preset.id}`}>{t("cta")}</Link>
          </Button>
        </div>
      </div>
      <div
        className={`flex flex-1 flex-col ${PREVIEW_FONT_VARIABLES}`}
        style={{ ...getCssVars(preset.theme_code, settings), fontFamily: "var(--font-sans)" }}
      >
        <theme.Header
          storeName={preset.theme_name}
          navOrder={settings.nav_order}
          locale={locale}
          homeHref="#"
          disableNav
        />
        <PreviewTabs home={homePanel} catalog={catalogPanel} product={productPanel} cart={cartPanel} />
        <theme.Footer storeName={preset.theme_name} />
      </div>
    </div>
  );
}
