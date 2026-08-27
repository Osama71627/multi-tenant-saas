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
  navOrder,
  locale,
  homeHref,
  cartSlot,
  disableNav = false,
}: {
  storeName: string;
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
        <Link href={homeHref ?? `/${locale}`} className="flex items-center gap-1.5 text-lg font-bold">
          <Zap className="h-4 w-4" style={{ color: "var(--sf-accent)" }} />
          {storeName}
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
