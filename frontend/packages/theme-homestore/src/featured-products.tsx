import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { HomestoreProductGrid } from "./product-grid";
import type { HomestoreProductListItem } from "./types";

export async function HomestoreFeaturedProducts({
  products,
  productHref,
  viewAllHref,
}: {
  products: HomestoreProductListItem[];
  productHref: (slug: string) => string;
  viewAllHref: string | null;
}) {
  if (!products.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 lg:px-8 lg:py-24">
      <div className="mb-12 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <span
            className="text-sm font-semibold uppercase tracking-widest"
            style={{ color: "var(--sf-secondary)" }}
          >
            {t("collection")}
          </span>
          <h2 className="mt-2 text-3xl font-bold text-neutral-900 sm:text-4xl">
            {t("featuredProducts")}
          </h2>
        </div>
        {viewAllHref ? (
          <Link
            href={viewAllHref}
            className="inline-flex items-center gap-1.5 text-sm font-semibold"
            style={{ color: "var(--sf-secondary)" }}
          >
            {t("viewAll")}
          </Link>
        ) : null}
      </div>
      <HomestoreProductGrid products={products.slice(0, 8)} productHref={productHref} />
    </section>
  );
}
