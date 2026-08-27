import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { FashionProductGrid } from "./product-grid";
import type { FashionProductListItem } from "./types";

export async function FashionFeaturedProducts({
  products,
  productHref,
  viewAllHref,
}: {
  products: FashionProductListItem[];
  productHref: (slug: string) => string;
  viewAllHref: string | null;
}) {
  if (!products.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="mx-auto max-w-6xl px-4 py-20">
      <div className="mb-10 text-center">
        <p className="text-xs font-medium uppercase tracking-[0.3em] text-gray-500">Shop the edit</p>
        <h2 className="mt-2 font-serif text-3xl">{t("featuredProducts")}</h2>
        {viewAllHref ? (
          <Link
            href={viewAllHref}
            className="mt-3 inline-block text-xs font-medium uppercase tracking-widest underline underline-offset-4"
          >
            {t("viewAll")}
          </Link>
        ) : null}
      </div>
      <FashionProductGrid products={products.slice(0, 8)} productHref={productHref} />
    </section>
  );
}
