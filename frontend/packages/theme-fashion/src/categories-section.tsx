import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { FashionCategory } from "./types";

/** A tracked-uppercase text list with hairline dividers, not Aurora's
 * rounded pill buttons -- the editorial-index convention. */
export async function FashionCategoriesSection({
  categories,
  categoryHref,
}: {
  categories: FashionCategory[];
  categoryHref: (slug: string) => string;
}) {
  if (!categories.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="border-t px-4 py-16">
      <div className="mx-auto max-w-6xl text-center">
        <h2 className="mb-8 text-xs font-medium uppercase tracking-[0.3em] text-gray-500">
          {t("categories")}
        </h2>
        <div className="flex flex-wrap items-center justify-center divide-x">
          {categories.map((category) => (
            <Link
              key={category.id}
              href={categoryHref(category.slug)}
              className="px-6 py-1 font-serif text-lg hover:text-gray-500"
            >
              {category.name}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
