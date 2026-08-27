import { AuroraProductCard } from "./product-card";
import type { AuroraProductListItem } from "./types";

/**
 * Phase B addition: the grid layout itself moves into the theme
 * component (was previously hardcoded in the consuming page's
 * className) so a theme can control density/spacing, not just card
 * design -- see @saas/theme-electronics's denser grid for why this
 * needed to become a real component.
 */
export function AuroraProductGrid({
  products,
  productHref,
}: {
  products: AuroraProductListItem[];
  productHref: (slug: string) => string;
}) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {products.map((product) => (
        <AuroraProductCard key={product.id} product={product} href={productHref(product.slug)} />
      ))}
    </div>
  );
}
