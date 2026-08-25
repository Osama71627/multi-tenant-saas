import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { AuroraCategory } from "./types";

export async function AuroraCategoriesSection({
  categories,
  categoryHref,
}: {
  categories: AuroraCategory[];
  categoryHref: (slug: string) => string;
}) {
  if (!categories.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <h2 className="mb-6 text-2xl font-semibold">{t("categories")}</h2>
      <div className="flex flex-wrap gap-3">
        {categories.map((category) => (
          <Link
            key={category.id}
            href={categoryHref(category.slug)}
            className="rounded-full border px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            {category.name}
          </Link>
        ))}
      </div>
    </section>
  );
}
