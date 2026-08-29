import { notFound } from "next/navigation";

import { getTheme } from "@/components/theme-registry";
import { getCategories, getProducts } from "@/lib/catalog";
import { currentHostname, getStorefrontContext } from "@/lib/theme";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const context = await getStorefrontContext();
  if (!context) notFound();

  const hostname = await currentHostname();
  const theme = getTheme(context.theme.theme_code);
  const settings = context.theme.settings;

  const needsProducts = settings.homepage_sections.includes("featured_products");
  const needsCategories = settings.homepage_sections.includes("categories");

  const [products, categories] = await Promise.all([
    needsProducts ? getProducts(hostname) : Promise.resolve([]),
    needsCategories ? getCategories(hostname) : Promise.resolve([]),
  ]);

  const sectionRenderers: Record<string, React.ReactNode> = {
    hero: (
      <theme.Hero
        headline={settings.hero_headline}
        subheadline={settings.hero_subheadline}
        shopHref={`/${locale}/products`}
      />
    ),
    featured_products: (
      <theme.FeaturedProducts
        products={products}
        productHref={(slug) => `/${locale}/products/${slug}`}
        viewAllHref={`/${locale}/products`}
      />
    ),
    categories: (
      <theme.Categories
        categories={categories}
        categoryHref={(slug) => `/${locale}/products?category=${slug}`}
      />
    ),
    newsletter: <theme.Newsletter />,
  };

  return (
    <div>
      {settings.homepage_sections.map((section) => (
        <div key={section}>{sectionRenderers[section]}</div>
      ))}
    </div>
  );
}
