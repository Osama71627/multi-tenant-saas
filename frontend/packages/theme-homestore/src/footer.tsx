import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { HomestoreSettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

/**
 * Dark, multi-column footer -- source design had a 4-column layout
 * (About+social / Links / Links / Newsletter mini-form) with social
 * icons all pointing at "#" (dead links -- no real social URLs
 * configured anywhere in this platform) -- dropped here rather than
 * shipping a fake affordance, same "no dead links" posture as every
 * other real decision in this project. Kept: brand + a real tagline,
 * real nav links, a real copyright bar.
 */
export async function HomestoreFooter({
  storeName,
  logoUrl,
  navOrder,
  locale,
  disableNav = false,
}: {
  storeName: string;
  logoUrl?: string | null;
  navOrder?: HomestoreSettings["nav_order"];
  locale?: string;
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");
  const tHome = await getTranslations("storefront.home");

  return (
    <footer className="bg-neutral-900 text-neutral-300">
      <div className="mx-auto max-w-7xl px-4 py-16 lg:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-1">
            {logoUrl ? (
              <span className="inline-block rounded-md bg-white/95 px-3 py-1.5">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={logoUrl} alt={storeName} className="h-7 w-auto object-contain" />
              </span>
            ) : (
              <p className="text-2xl font-bold tracking-tight text-white">{storeName}</p>
            )}
            <p className="max-w-sm text-sm leading-relaxed text-neutral-400">
              {tHome("footerTagline")}
            </p>
          </div>

          {navOrder?.length && locale ? (
            <div className="lg:col-span-1">
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-widest text-white">
                {t("shop")}
              </h3>
              <nav className="flex flex-col gap-2.5">
                {navOrder.map((item) =>
                  disableNav ? (
                    <span key={item} className="text-sm text-neutral-400">
                      {t(item)}
                    </span>
                  ) : (
                    <Link
                      key={item}
                      href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
                      className="text-sm text-neutral-400 transition-colors hover:text-white"
                    >
                      {t(item)}
                    </Link>
                  )
                )}
              </nav>
            </div>
          ) : null}
        </div>
      </div>
      <div className="border-t border-white/10 px-4 py-6 text-center text-xs text-neutral-500">
        © {new Date().getFullYear()} {storeName}
      </div>
    </footer>
  );
}
