import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { FashionSettings } from "./types";

const NAV_HREFS: Record<string, string> = {
  shop: "/products",
  about: "/about",
  contact: "/contact",
};

/** Dark, editorial footer -- the large wordmark + small print
 * convention, structurally different from Aurora's single-line
 * light-background footer. Expanded with real nav links + the store's
 * own logo (when uploaded) -- the previous version was just a wordmark
 * and a copyright line, with no way back into the catalog from here. */
export async function FashionFooter({
  storeName,
  logoUrl,
  navOrder,
  locale,
  disableNav = false,
}: {
  storeName: string;
  /** See FashionHeader's identical prop for the full "logo was
   * write-only" story -- same fallback-to-text-wordmark behavior. */
  logoUrl?: string | null;
  /** Optional: the dashboard's live-preview host renders this footer
   * with no `navOrder`/`locale` at all (StorePreviewPage only ever
   * calls `<theme.Footer storeName={...} />`) -- the nav row simply
   * doesn't render in that case, same "no dead affordance" posture as
   * FashionHeader's `disableNav`. */
  navOrder?: FashionSettings["nav_order"];
  locale?: string;
  disableNav?: boolean;
}) {
  const t = await getTranslations("storefront.nav");

  return (
    <footer
      className="px-4 py-16 text-center text-white"
      style={{ backgroundColor: "var(--sf-primary)" }}
    >
      {logoUrl ? (
        // A light backing chip -- this footer is a dark block
        // (`--sf-primary` background), and an uploaded logo is usually
        // designed for a light background and would otherwise disappear
        // against it. Same fix as ElectronicsHeader/Footer's identical
        // dark-surface problem -- see that comment for the full reasoning.
        <span className="mx-auto mb-4 inline-block rounded-md bg-white/95 px-3 py-1.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={logoUrl} alt={storeName} className="h-7 w-auto object-contain" />
        </span>
      ) : (
        <p className="font-serif text-2xl tracking-wide">{storeName}</p>
      )}

      {navOrder?.length && locale ? (
        <nav className="mt-6 flex flex-wrap items-center justify-center gap-x-8 gap-y-2">
          {navOrder.map((item) =>
            disableNav ? (
              <span
                key={item}
                className="text-xs font-medium uppercase tracking-[0.2em] text-white/60"
              >
                {t(item)}
              </span>
            ) : (
              <Link
                key={item}
                href={`/${locale}${NAV_HREFS[item] ?? "/"}`}
                className="text-xs font-medium uppercase tracking-[0.2em] text-white/70 transition-colors hover:text-white"
              >
                {t(item)}
              </Link>
            )
          )}
        </nav>
      ) : null}

      <p className="mt-8 text-xs uppercase tracking-[0.3em] text-white/50">
        © {new Date().getFullYear()} {storeName}
      </p>
    </footer>
  );
}
