import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { LuxuryCategory } from "./types";

/** Thin-divided, tracked-caps text row, centered -- consistent with
 * this theme's minimal, no-background-fill surfaces everywhere else. */
export async function LuxuryCategoriesSection({
  categories,
  categoryHref,
}: {
  categories: LuxuryCategory[];
  categoryHref: (slug: string) => string;
}) {
  if (!categories.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="border-t border-gray-100 px-4 py-16 text-center">
      <h2 className="mb-8 text-xs font-light uppercase tracking-[0.35em] text-gray-500">
        {t("categories")}
      </h2>
      <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
        {categories.map((category) => (
          <Link
            key={category.id}
            href={categoryHref(category.slug)}
            className="text-xs font-light uppercase tracking-[0.2em] text-gray-600 hover:text-black"
          >
            {category.name}
          </Link>
        ))}
      </div>
    </section>
  );
}
