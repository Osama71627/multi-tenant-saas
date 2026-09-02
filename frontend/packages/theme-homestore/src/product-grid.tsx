import { HomestoreProductCard } from "./product-card";
import type { HomestoreProductListItem } from "./types";

/** Standard retail 4-column grid at desktop, registered on the theme
 * object so pages never hardcode a grid className themselves -- same
 * reasoning as every other theme's own ProductGrid. */
export function HomestoreProductGrid({
  products,
  productHref,
}: {
  products: HomestoreProductListItem[];
  productHref: (slug: string) => string;
}) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
      {products.map((product) => (
        <HomestoreProductCard key={product.id} product={product} href={productHref(product.slug)} />
      ))}
    </div>
  );
}
