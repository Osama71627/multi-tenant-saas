import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { LuxuryProductGrid } from "./product-grid";
import type { LuxuryProductListItem } from "./types";

export async function LuxuryFeaturedProducts({
  products,
  productHref,
  viewAllHref,
}: {
  products: LuxuryProductListItem[];
  productHref: (slug: string) => string;
  viewAllHref: string | null;
}) {
  if (!products.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="mx-auto max-w-5xl px-4 py-24">
      <div className="mb-12 text-center">
        <h2 className="text-xs font-light uppercase tracking-[0.35em] text-gray-500">
          {t("featuredProducts")}
        </h2>
        {viewAllHref ? (
          <Link
            href={viewAllHref}
            className="mt-4 inline-block text-xs font-light uppercase tracking-[0.2em] text-gray-400 hover:text-gray-700"
          >
            {t("viewAll")}
          </Link>
        ) : null}
      </div>
      <LuxuryProductGrid products={products.slice(0, 6)} productHref={productHref} />
    </section>
  );
}
