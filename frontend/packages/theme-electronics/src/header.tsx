import { Menu, Zap } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import type { ElectronicsSettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

/** Dark, compact "tech retailer" header -- solid dark bar (not white
 * like Aurora/Fashion), bold uppercase nav, a small accent-colored
 * spark icon next to the wordmark. */
export async function ElectronicsHeader({
  storeName,
  logoUrl,
  navOrder,
  locale,
  homeHref,
  cartSlot,
  disableNav = false,
}: {
  storeName: string;
  /** See @saas/theme-aurora's AuroraHeader for the full "logo was
   * write-only" story -- same optional prop, same fallback-to-text-
   * wordmark behavior here. */
  logoUrl?: string | null;
  navOrder: ElectronicsSettings["nav_order"];
  locale: string;
  homeHref?: string;
  cartSlot?: ReactNode;
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");

  const navItems = navOrder.map((item) =>
    disableNav ? (
      <span key={item} className="text-sm font-bold uppercase text-white/60">
        {t(item)}
      </span>
    ) : (
      <Link
        key={item}
        href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
        className="text-sm font-bold uppercase text-white/80 hover:text-white"
      >
        {t(item)}
      </Link>
    )
  );

  return (
    <header className="text-white" style={{ backgroundColor: "var(--sf-primary)" }}>
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-3">
        <Link href={homeHref ?? `/${locale}`} className="flex items-center gap-1.5">
          {logoUrl ? (
            // A light backing chip -- this header is a dark bar
            // (`--sf-primary` background), and an uploaded logo is
            // usually designed for a light background (dark artwork/
            // text) and would otherwise disappear against it. No way to
            // know the logo's own colors ahead of time, so this is the
            // safe default rather than risking an invisible logo.
            <span className="rounded-md bg-white/95 px-2 py-1">
              {/* eslint-disable-next-line @next/next/no-img-element -- a real,
                  absolute, cross-origin URL (Django's own media host). */}
              <img src={logoUrl} alt={storeName} className="h-6 w-auto object-contain" />
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-lg font-bold">
              <Zap className="h-4 w-4" style={{ color: "var(--sf-accent)" }} />
              {storeName}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-5">
          <nav className="hidden items-center gap-6 sm:flex">{navItems}</nav>
          {cartSlot}
          <label
            htmlFor="electronics-nav-toggle"
            className="cursor-pointer p-1 text-white sm:hidden"
            aria-label="Menu"
          >
            <Menu className="h-5 w-5" />
          </label>
        </div>
      </div>
      <input type="checkbox" id="electronics-nav-toggle" className="peer hidden" />
      <nav className="hidden flex-col gap-2 border-t border-white/10 px-4 py-3 peer-checked:flex sm:hidden">
        {navItems}
      </nav>
    </header>
  );
}
