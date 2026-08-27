import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { ElectronicsProductGrid } from "./product-grid";
import type { ElectronicsProductListItem } from "./types";

export async function ElectronicsFeaturedProducts({
  products,
  productHref,
  viewAllHref,
}: {
  products: ElectronicsProductListItem[];
  productHref: (slug: string) => string;
  viewAllHref: string | null;
}) {
  if (!products.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="mx-auto max-w-6xl px-4 py-12">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-black uppercase tracking-tight">{t("featuredProducts")}</h2>
        {viewAllHref ? (
          <Link
            href={viewAllHref}
            className="text-sm font-bold"
            style={{ color: "var(--sf-secondary)" }}
          >
            {t("viewAll")} →
          </Link>
        ) : null}
      </div>
      <ElectronicsProductGrid products={products.slice(0, 10)} productHref={productHref} />
    </section>
  );
}
