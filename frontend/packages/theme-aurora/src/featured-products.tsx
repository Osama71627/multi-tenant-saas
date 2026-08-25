import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AuroraProductCard } from "./product-card";
import type { AuroraProductListItem } from "./types";

export async function AuroraFeaturedProducts({
  products,
  productHref,
  viewAllHref,
}: {
  products: AuroraProductListItem[];
  productHref: (slug: string) => string;
  /** `null` hides the "View all" link entirely (preview mode has no
   * real catalog-listing route to send it to). */
  viewAllHref: string | null;
}) {
  if (!products.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold">{t("featuredProducts")}</h2>
        {viewAllHref ? (
          <Link href={viewAllHref} className="text-sm underline underline-offset-4">
            {t("viewAll")}
          </Link>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {products.slice(0, 8).map((product) => (
          <AuroraProductCard key={product.id} product={product} href={productHref(product.slug)} />
        ))}
      </div>
    </section>
  );
}
