import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { FashionCategory } from "./types";

// No category-image pipeline exists in this project (same honest
// constraint FashionProductCard's own comment documents for products)
// -- these three gradient combinations, cycled deterministically by
// index, are what stand in for real category photography. Kept to the
// theme's own three tokens (never a hardcoded colour) so every store's
// tiles are unique to its own palette, not a generic placeholder look.
const TILE_GRADIENTS = [
  "linear-gradient(135deg, var(--sf-primary), var(--sf-secondary))",
  "linear-gradient(135deg, var(--sf-secondary), var(--sf-accent))",
  "linear-gradient(135deg, var(--sf-accent), var(--sf-primary))",
];

/**
 * Real tile cards -- browsable image-style tiles (a gradient stand-in,
 * see TILE_GRADIENTS's own comment), not the previous plain
 * uppercase-text-list-with-dividers treatment, which read as an
 * unstyled admin index rather than a shoppable category rail.
 */
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
    <section className="border-t px-4 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-10 text-center text-xs font-medium uppercase tracking-[0.3em] text-gray-500">
          {t("categories")}
        </h2>
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
          {categories.map((category, index) => (
            <Link
              key={category.id}
              href={categoryHref(category.slug)}
              className="group relative flex h-40 items-center justify-center overflow-hidden rounded-lg transition-transform duration-300 hover:-translate-y-1 sm:h-52"
              style={{ background: TILE_GRADIENTS[index % TILE_GRADIENTS.length] }}
            >
              <div className="absolute inset-0 bg-black/10 transition-colors duration-300 group-hover:bg-black/25" />
              <span className="relative font-serif text-xl text-white sm:text-2xl">
                {category.name}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
