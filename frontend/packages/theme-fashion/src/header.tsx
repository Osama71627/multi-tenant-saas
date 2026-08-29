import { Menu } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import type { FashionSettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

/**
 * Editorial-fashion header: serif wordmark, uppercase letter-spaced nav
 * -- deliberately visually distinct from Aurora's plain sans header,
 * same prop contract (`storeName`/`navOrder`/`locale`/`homeHref`/
 * `cartSlot`/`disableNav`) so the registry can swap it in without the
 * consuming page knowing which theme is active.
 */
export async function FashionHeader({
  storeName,
  logoUrl,
  navOrder,
  locale,
  homeHref,
  cartSlot,
  disableNav = false,
}: {
  storeName: string;
  /** Real gap found live: this header only ever had the store NAME to
   * render (plain serif text wordmark), even for a store with a real
   * logo uploaded (Store.logo, Phase F's business-info step) -- see
   * apps.themes.serializers.StorefrontStoreSerializer.logo's own
   * comment for the backend half of this fix. `undefined`/`null`/`""`
   * all fall back to the text wordmark exactly as before. */
  logoUrl?: string | null;
  navOrder: FashionSettings["nav_order"];
  locale: string;
  homeHref?: string;
  cartSlot?: ReactNode;
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");

  const navItems = navOrder.map((item) =>
    disableNav ? (
      <span key={item} className="text-xs font-medium uppercase tracking-[0.2em] text-gray-500">
        {t(item)}
      </span>
    ) : (
      <Link
        key={item}
        href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
        className="text-xs font-medium uppercase tracking-[0.2em] text-gray-700 transition-colors hover:text-black"
      >
        {t(item)}
      </Link>
    )
  );

  return (
    <header className="sticky top-0 z-30 border-b bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-6">
        <Link href={homeHref ?? `/${locale}`} className="flex items-center">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- a real,
            // absolute, cross-origin URL (Django's own media host).
            <img src={logoUrl} alt={storeName} className="h-9 w-auto object-contain" />
          ) : (
            <span
              className="font-serif text-2xl tracking-wide"
              style={{ color: "var(--sf-primary)" }}
            >
              {storeName}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-6">
          <nav className="hidden items-center gap-8 sm:flex">{navItems}</nav>
          {cartSlot}
          <label
            htmlFor="fashion-nav-toggle"
            className="cursor-pointer p-1 text-gray-700 sm:hidden"
            aria-label="Menu"
          >
            <Menu className="h-5 w-5" />
          </label>
        </div>
      </div>
      <input type="checkbox" id="fashion-nav-toggle" className="peer hidden" />
      <nav className="hidden flex-col gap-3 border-t px-4 py-4 peer-checked:flex sm:hidden">
        {navItems}
      </nav>
    </header>
  );
}
