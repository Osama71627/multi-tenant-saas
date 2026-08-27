import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { ElectronicsCategory } from "./types";

/** Dark, bold, square-cornered category buttons -- the "tech
 * department list" convention, unlike Aurora's rounded pill or
 * Fashion's tracked text list. */
export async function ElectronicsCategoriesSection({
  categories,
  categoryHref,
}: {
  categories: ElectronicsCategory[];
  categoryHref: (slug: string) => string;
}) {
  if (!categories.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="px-4 py-12" style={{ backgroundColor: "var(--sf-primary)" }}>
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-6 text-xl font-black uppercase tracking-tight text-white">
          {t("categories")}
        </h2>
        <div className="flex flex-wrap gap-2">
          {categories.map((category) => (
            <Link
              key={category.id}
              href={categoryHref(category.slug)}
              className="rounded bg-white/10 px-4 py-2 text-sm font-bold uppercase text-white hover:bg-white/20"
            >
              {category.name}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
