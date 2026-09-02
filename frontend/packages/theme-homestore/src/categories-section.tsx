import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { HomestoreCategory } from "./types";

const TILE_GRADIENTS = [
  "linear-gradient(135deg, var(--sf-primary), var(--sf-secondary))",
  "linear-gradient(135deg, var(--sf-secondary), var(--sf-accent))",
  "linear-gradient(135deg, var(--sf-accent), var(--sf-primary))",
];

/**
 * Real photographic tiles when `image_url` is set (fixture-only --
 * see HomestoreCategory.image_url's own comment for why a real
 * merchant's categories never have one today), a gradient tile
 * cycling through the store's own tokens otherwise -- same
 * "considered placeholder" posture as every other theme's Categories
 * section, never a flat gray box.
 */
export async function HomestoreCategoriesSection({
  categories,
  categoryHref,
}: {
  categories: HomestoreCategory[];
  categoryHref: (slug: string) => string;
}) {
  if (!categories.length) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section className="bg-neutral-50 px-4 py-16 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 text-center">
          <span
            className="text-sm font-semibold uppercase tracking-widest"
            style={{ color: "var(--sf-secondary)" }}
          >
            {t("browse")}
          </span>
          <h2 className="mt-2 text-3xl font-bold text-neutral-900 sm:text-4xl">
            {t("categories")}
          </h2>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:gap-6 lg:grid-cols-6">
          {categories.map((category, index) => (
            <Link
              key={category.id}
              href={categoryHref(category.slug)}
              className="group relative block aspect-[4/5] overflow-hidden rounded-2xl"
            >
              {category.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={category.image_url}
                  alt={category.name}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
                />
              ) : (
                <div
                  className="h-full w-full transition-transform duration-500 group-hover:scale-110"
                  style={{ background: TILE_GRADIENTS[index % TILE_GRADIENTS.length] }}
                />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
              <div className="absolute bottom-0 left-0 right-0 p-4">
                <h3 className="text-sm font-semibold text-white md:text-base">{category.name}</h3>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
