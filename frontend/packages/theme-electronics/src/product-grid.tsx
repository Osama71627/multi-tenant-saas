import { ElectronicsProductCard } from "./product-card";
import type { ElectronicsProductListItem } from "./types";

/** Denser grid than Aurora/Fashion -- up to 5 columns at desktop with
 * a tighter gap, the "browse a big catalog fast" electronics-retail
 * convention. */
export function ElectronicsProductGrid({
  products,
  productHref,
}: {
  products: ElectronicsProductListItem[];
  productHref: (slug: string) => string;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {products.map((product) => (
        <ElectronicsProductCard
          key={product.id}
          product={product}
          href={productHref(product.slug)}
        />
      ))}
    </div>
  );
}
