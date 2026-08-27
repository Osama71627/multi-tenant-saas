import { LuxuryProductCard } from "./product-card";
import type { LuxuryProductListItem } from "./types";

/** Only 3 columns at desktop with wide gaps -- fewer, larger products
 * per row than Aurora's 4 or Electronics's 5, the "let each piece
 * breathe" convention. */
export function LuxuryProductGrid({
  products,
  productHref,
}: {
  products: LuxuryProductListItem[];
  productHref: (slug: string) => string;
}) {
  return (
    <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:gap-10">
      {products.map((product) => (
        <LuxuryProductCard key={product.id} product={product} href={productHref(product.slug)} />
      ))}
    </div>
  );
}
