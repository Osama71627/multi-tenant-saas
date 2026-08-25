import Link from "next/link";

import type { AuroraProductListItem } from "./types";

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

export function AuroraProductCard({
  product,
  href,
}: {
  product: AuroraProductListItem;
  /** The real storefront links to `/${locale}/products/${slug}`; preview
   * mode has no real product route, so it passes `#` (or a disabled
   * href) instead -- same component either way. */
  href: string;
}) {
  const onSale =
    product.compare_at_price_amount != null &&
    product.price_amount != null &&
    product.compare_at_price_amount > product.price_amount;

  return (
    <Link
      href={href}
      className="group block overflow-hidden rounded-lg border transition-shadow hover:shadow-md"
    >
      <div className="flex aspect-square items-center justify-center bg-gray-100 text-gray-300">
        <span className="text-sm">{product.name}</span>
      </div>
      <div className="space-y-1 p-3">
        <p className="truncate text-sm font-medium text-gray-900">{product.name}</p>
        {product.price_amount != null && product.currency ? (
          <p className="flex items-center gap-2 text-sm">
            <span style={{ color: "var(--sf-primary)" }} className="font-semibold">
              {formatMoney(product.price_amount, product.currency)}
            </span>
            {onSale && product.compare_at_price_amount != null ? (
              <span className="text-gray-400 line-through">
                {formatMoney(product.compare_at_price_amount, product.currency)}
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
