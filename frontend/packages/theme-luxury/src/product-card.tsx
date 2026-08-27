import Link from "next/link";

import type { LuxuryProductListItem } from "./types";

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

/** Square image, small tracked-caps name, understated price -- no
 * badges at all, deliberately (the "quiet luxury" convention never
 * shouts "Sale"). Even a discounted price is shown quietly, without
 * Fashion's ribbon or Electronics's colored chip. */
export function LuxuryProductCard({
  product,
  href,
}: {
  product: LuxuryProductListItem;
  href: string;
}) {
  const onSale =
    product.compare_at_price_amount != null &&
    product.price_amount != null &&
    product.compare_at_price_amount > product.price_amount;

  return (
    <Link href={href} className="group block">
      <div className="flex aspect-square items-center justify-center bg-gray-50 text-gray-300">
        <span className="text-xs font-light tracking-widest">{product.name}</span>
      </div>
      <div className="mt-4 space-y-1 text-center">
        <p className="truncate text-xs font-light uppercase tracking-[0.15em] text-gray-700">
          {product.name}
        </p>
        {product.price_amount != null && product.currency ? (
          <p className="flex items-center justify-center gap-2 text-sm font-light text-gray-900">
            <span>{formatMoney(product.price_amount, product.currency)}</span>
            {onSale && product.compare_at_price_amount != null ? (
              <span className="text-gray-300 line-through">
                {formatMoney(product.compare_at_price_amount, product.currency)}
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
