import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { getTheme } from "@/components/theme-registry";
import { getProducts } from "@/lib/catalog";
import { currentHostname, getStorefrontContext } from "@/lib/theme";

export default async function ProductsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ category?: string }>;
}) {
  const { locale } = await params;
  const { category } = await searchParams;
  const context = await getStorefrontContext();
  if (!context) notFound();

  const hostname = await currentHostname();
  const theme = getTheme(context.theme.theme_code);
  const products = await getProducts(hostname, category);
  const t = await getTranslations("storefront.product");

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      {!products.length ? (
        <div className="py-20 text-center">
          <h1 className="text-lg font-semibold">{t("noProducts")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("noProductsDescription")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {products.map((product) => (
            <theme.ProductCard
              key={product.id}
              product={product}
              href={`/${locale}/products/${product.slug}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
