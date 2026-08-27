import { FashionProductCard } from "./product-card";
import type { FashionProductListItem } from "./types";

/**
 * Wide-gapped 4-column grid at desktop -- the editorial "let the
 * product breathe" convention, wider gaps than Aurora's tighter
 * general-purpose grid. Registered on the theme object so pages never
 * hardcode a grid className themselves (see the registry's own note on
 * why this exists as a real component, not just a Tailwind class the
 * page picks).
 */
export function FashionProductGrid({
  products,
  productHref,
}: {
  products: FashionProductListItem[];
  productHref: (slug: string) => string;
}) {
  return (
    <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4 lg:gap-8">
      {products.map((product) => (
        <FashionProductCard key={product.id} product={product} href={productHref(product.slug)} />
      ))}
    </div>
  );
}
