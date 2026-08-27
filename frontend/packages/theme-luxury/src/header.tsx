import { Menu } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import type { LuxurySettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

/** Ultra-minimal, centered header -- wordmark centered on its own row,
 * small-caps nav on a second row below it, generous vertical padding,
 * a single hairline border. The "quiet luxury" convention: no bold
 * color blocks anywhere, unlike Fashion's dark bar or Electronics's
 * gradient/dark surfaces. */
export async function LuxuryHeader({
  storeName,
  navOrder,
  locale,
  homeHref,
  cartSlot,
  disableNav = false,
}: {
  storeName: string;
  navOrder: LuxurySettings["nav_order"];
  locale: string;
  homeHref?: string;
  cartSlot?: ReactNode;
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");

  const navItems = navOrder.map((item) =>
    disableNav ? (
      <span key={item} className="text-[11px] font-light uppercase tracking-[0.3em] text-gray-400">
        {t(item)}
      </span>
    ) : (
      <Link
        key={item}
        href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
        className="text-[11px] font-light uppercase tracking-[0.3em] text-gray-600 hover:text-black"
      >
        {t(item)}
      </Link>
    )
  );

  return (
    <header className="border-b border-gray-100">
      <div className="flex flex-col items-center gap-4 py-8">
        <Link
          href={homeHref ?? `/${locale}`}
          className="text-xl font-light tracking-[0.15em]"
          style={{ color: "var(--sf-primary)" }}
        >
          {storeName}
        </Link>
        <div className="flex items-center gap-8">
          <nav className="hidden items-center gap-8 sm:flex">{navItems}</nav>
          {cartSlot}
          <label
            htmlFor="luxury-nav-toggle"
            className="cursor-pointer p-1 text-gray-600 sm:hidden"
            aria-label="Menu"
          >
            <Menu className="h-4 w-4" />
          </label>
        </div>
      </div>
      <input type="checkbox" id="luxury-nav-toggle" className="peer hidden" />
      <nav className="hidden flex-col items-center gap-3 border-t border-gray-100 py-4 peer-checked:flex sm:hidden">
        {navItems}
      </nav>
    </header>
  );
}
