import { Menu, Truck } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import type { HomestoreSettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

/**
 * Premium "home goods retailer" header -- a slim announcement bar
 * above a clean white bar, bold wordmark, generously spaced nav.
 * Source design: a real, previously-built storefront the user brought
 * (github.com/Osama71627/Online_shop) had a scroll-reactive
 * transparent-over-hero header with a live search bar and a hover mega
 * -menu; simplified here to a plain sticky bar with flat nav -- no
 * backend search endpoint exists in this project yet (a fake search
 * box would be a dead affordance), and the shared theme-registry
 * `Header` contract doesn't carry category data to build a real mega
 * -menu from. Same prop contract as every other theme
 * (`storeName`/`logoUrl`/`navOrder`/`locale`/`homeHref`/`cartSlot`/
 * `disableNav`) so the registry can swap it in without the consuming
 * page knowing which theme is active.
 */
export async function HomestoreHeader({
  storeName,
  logoUrl,
  navOrder,
  locale,
  homeHref,
  cartSlot,
  disableNav = false,
}: {
  storeName: string;
  logoUrl?: string | null;
  navOrder: HomestoreSettings["nav_order"];
  locale: string;
  homeHref?: string;
  cartSlot?: ReactNode;
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");
  const tHome = await getTranslations("storefront.home");

  const navItems = navOrder.map((item) =>
    disableNav ? (
      <span key={item} className="text-sm font-medium text-neutral-600">
        {t(item)}
      </span>
    ) : (
      <Link
        key={item}
        href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
        className="text-sm font-medium text-neutral-700 transition-colors hover:text-neutral-950"
      >
        {t(item)}
      </Link>
    )
  );

  return (
    <header className="sticky top-0 z-30">
      <div
        className="flex items-center justify-center gap-2 px-4 py-2 text-center text-xs font-light tracking-wide text-white"
        style={{ backgroundColor: "var(--sf-primary)" }}
      >
        <Truck className="h-3.5 w-3.5 opacity-70" />
        {tHome("freeShippingBanner")}
      </div>
      <div className="border-b bg-white/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-4 py-4 lg:px-8">
          <Link href={homeHref ?? `/${locale}`} className="flex items-center">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element -- a real,
              // absolute, cross-origin URL (Django's own media host).
              <img src={logoUrl} alt={storeName} className="h-9 w-auto object-contain" />
            ) : (
              <span className="text-2xl font-bold tracking-tight text-neutral-900">
                {storeName}
              </span>
            )}
          </Link>
          <div className="flex items-center gap-6">
            <nav className="hidden items-center gap-8 sm:flex">{navItems}</nav>
            {cartSlot}
            <label
              htmlFor="homestore-nav-toggle"
              className="cursor-pointer p-1 text-neutral-700 sm:hidden"
              aria-label="Menu"
            >
              <Menu className="h-5 w-5" />
            </label>
          </div>
        </div>
        <input type="checkbox" id="homestore-nav-toggle" className="peer hidden" />
        <nav className="hidden flex-col gap-3 border-t px-4 py-4 peer-checked:flex sm:hidden">
          {navItems}
        </nav>
      </div>
    </header>
  );
}
