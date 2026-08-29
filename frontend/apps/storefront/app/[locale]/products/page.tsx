import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getTheme } from "@/components/theme-registry";
import { getCategories, getProducts, type StorefrontSort } from "@/lib/catalog";
import { currentHostname, getStorefrontContext } from "@/lib/theme";

const SORT_OPTIONS: StorefrontSort[] = ["name", "newest", "price_asc", "price_desc"];

function buildHref(locale: string, category?: string, sort?: string): string {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (sort && sort !== "name") params.set("sort", sort);
  const qs = params.toString();
  return `/${locale}/products${qs ? `?${qs}` : ""}`;
}

/**
 * Real gap found live: this page used to render EITHER an empty state
 * or a bare product grid with no page chrome at all -- no title, no
 * way to browse by category, no sort. Server-rendered category chips +
 * sort links (plain `<a>`s, not a client-side `<select>`) -- same
 * "minimal JS, server component first" posture the rest of this app
 * already follows (see e.g. FashionHeader's checkbox-toggled mobile nav).
 */
export default async function ProductsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ category?: string; sort?: string }>;
}) {
  const { locale } = await params;
  const { category, sort: sortParam } = await searchParams;
  const sort: StorefrontSort = SORT_OPTIONS.includes(sortParam as StorefrontSort)
    ? (sortParam as StorefrontSort)
    : "name";
  const context = await getStorefrontContext();
  if (!context) notFound();

  const hostname = await currentHostname();
  const theme = getTheme(context.theme.theme_code);
  const [products, categories] = await Promise.all([
    getProducts(hostname, category, sort),
    getCategories(hostname),
  ]);
  const t = await getTranslations("storefront.product");
  const tSort = await getTranslations("storefront.sort");

  const activeCategory = categories.find((c) => c.slug === category);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="mb-8 flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold" style={{ color: "var(--sf-primary)" }}>
            {activeCategory?.name ?? t("allProducts")}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {t("productCount", { count: products.length })}
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-sm">
          <span className="text-gray-500">{tSort("label")}</span>
          {SORT_OPTIONS.map((option) => (
            <Link
              key={option}
              href={buildHref(locale, category, option)}
              className={
                option === sort
                  ? "rounded-full px-3 py-1 font-medium text-white"
                  : "rounded-full px-3 py-1 text-gray-600 hover:text-gray-950"
              }
              style={option === sort ? { backgroundColor: "var(--sf-primary)" } : undefined}
            >
              {tSort(option)}
            </Link>
          ))}
        </div>
      </div>

      {categories.length ? (
        <div className="mb-8 flex flex-wrap gap-2">
          <Link
            href={buildHref(locale, undefined, sort)}
            className={
              !category
                ? "rounded-full border px-4 py-1.5 text-sm font-medium text-white"
                : "rounded-full border px-4 py-1.5 text-sm text-gray-600 hover:border-gray-400"
            }
            style={!category ? { backgroundColor: "var(--sf-primary)", borderColor: "var(--sf-primary)" } : undefined}
          >
            {t("allCategories")}
          </Link>
          {categories.map((cat) => (
            <Link
              key={cat.id}
              href={buildHref(locale, cat.slug, sort)}
              className={
                cat.slug === category
                  ? "rounded-full border px-4 py-1.5 text-sm font-medium text-white"
                  : "rounded-full border px-4 py-1.5 text-sm text-gray-600 hover:border-gray-400"
              }
              style={
                cat.slug === category
                  ? { backgroundColor: "var(--sf-primary)", borderColor: "var(--sf-primary)" }
                  : undefined
              }
            >
              {cat.name}
            </Link>
          ))}
        </div>
      ) : null}

      {!products.length ? (
        <div className="py-20 text-center">
          <h2 className="text-lg font-semibold">{t("noProducts")}</h2>
          <p className="mt-1 text-sm text-gray-500">{t("noProductsDescription")}</p>
        </div>
      ) : (
        <theme.ProductGrid
          products={products}
          productHref={(slug) => `/${locale}/products/${slug}`}
        />
      )}
    </div>
  );
}
