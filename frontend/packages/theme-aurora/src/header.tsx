import { Menu } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import type { AuroraSettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

export async function AuroraHeader({
  storeName,
  logoUrl,
  navOrder,
  locale,
  homeHref,
  cartSlot,
  disableNav = false,
}: {
  storeName: string;
  /** Real gap found live: every theme's header only ever had the store
   * NAME to render (plain text wordmark), even for a store with a real
   * logo uploaded (Store.logo, Phase F's business-info step) -- see
   * apps.themes.serializers.StorefrontStoreSerializer.logo's own
   * comment for the backend half of this fix. `undefined`/`null`/`""`
   * all fall back to the text wordmark exactly as before. */
  logoUrl?: string | null;
  navOrder: AuroraSettings["nav_order"];
  locale: string;
  /** Where the store-name/logo link points. Defaults to `/${locale}`
   * (the real storefront's home) -- preview mode overrides this since
   * there's no real home route to link to there. */
  homeHref?: string;
  /** The real storefront injects its live cart-count link here;
   * preview mode passes nothing (there's no real cart to show), and
   * every OTHER nav item/behavior is still the exact same component. */
  cartSlot?: ReactNode;
  /** The real storefront's nav items link to its own `/products`,
   * `/about`, `/contact` routes. The dashboard's live-preview host has
   * no such routes, so it sets this to render plain (non-clickable)
   * labels instead of dead links -- same visual nav, no fake affordance. */
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");

  const navItems = navOrder.map((item) =>
    disableNav ? (
      <span key={item} className="text-sm font-medium text-gray-700">
        {t(item)}
      </span>
    ) : (
      <Link
        key={item}
        href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
        className="text-sm font-medium text-gray-700 hover:text-gray-950"
      >
        {t(item)}
      </Link>
    )
  );

  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-4">
        <Link href={homeHref ?? `/${locale}`} className="flex items-center">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- a real,
            // absolute, cross-origin URL (Django's own media host, see
            // apps.themes.serializers.StorefrontStoreSerializer.get_logo).
            <img src={logoUrl} alt={storeName} className="h-8 w-auto object-contain" />
          ) : (
            <span className="text-lg font-bold" style={{ color: "var(--sf-primary)" }}>
              {storeName}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-4">
          {/* Desktop/tablet: inline nav. Hidden below `sm` -- collapses
              into the checkbox-toggled panel below instead. CSS-only
              (no client JS) so this stays a plain Server Component. */}
          <nav className="hidden items-center gap-6 sm:flex">{navItems}</nav>
          {cartSlot}
          <label
            htmlFor="aurora-nav-toggle"
            className="cursor-pointer p-1 text-gray-700 sm:hidden"
            aria-label="Menu"
          >
            <Menu className="h-5 w-5" />
          </label>
        </div>
      </div>
      <input type="checkbox" id="aurora-nav-toggle" className="peer hidden" />
      <nav className="hidden flex-col gap-1 border-t px-4 py-3 peer-checked:flex sm:hidden">
        {navItems}
      </nav>
    </header>
  );
}
