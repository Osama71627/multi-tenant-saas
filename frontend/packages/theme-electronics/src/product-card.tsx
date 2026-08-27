import Link from "next/link";

import type { ElectronicsProductListItem } from "./types";

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

/** Cosmetic-only badge pick (no backend field for this) -- a sale
 * price always wins the "Sale" badge; otherwise alternates "New" and
 * "Best Seller" deterministically by id so the same product always
 * shows the same badge on every render, never randomly per request. */
function badgeFor(product: ElectronicsProductListItem, onSale: boolean): { label: string; tone: string } {
  if (onSale) return { label: "Sale", tone: "var(--sf-accent)" };
  const charSum = [...product.id].reduce((sum, c) => sum + c.charCodeAt(0), 0);
  return charSum % 2 === 0
    ? { label: "New", tone: "var(--sf-secondary)" }
    : { label: "Best Seller", tone: "#059669" };
}

/** Compact, square-image card with a top-corner badge and a mono-font
 * price row -- the "spec sheet" electronics-retail convention,
 * structurally distinct from Aurora's plain card and Fashion's
 * portrait/ribbon card. */
export function ElectronicsProductCard({
  product,
  href,
}: {
  product: ElectronicsProductListItem;
  href: string;
}) {
  const onSale =
    product.compare_at_price_amount != null &&
    product.price_amount != null &&
    product.compare_at_price_amount > product.price_amount;
  const badge = badgeFor(product, onSale);

  return (
    <Link
      href={href}
      className="group block overflow-hidden rounded-md border border-gray-200 transition-colors hover:border-gray-400"
    >
      <div className="relative flex aspect-square items-center justify-center bg-gray-100 text-gray-300">
        <span className="px-2 text-center text-xs">{product.name}</span>
        <span
          className="absolute start-2 top-2 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase text-white"
          style={{ backgroundColor: badge.tone }}
        >
          {badge.label}
        </span>
      </div>
      <div className="space-y-1 p-2.5">
        <p className="truncate text-xs font-semibold text-gray-900">{product.name}</p>
        {product.price_amount != null && product.currency ? (
          <p className="flex items-center gap-1.5 font-mono text-sm">
            <span className="font-bold" style={{ color: "var(--sf-primary)" }}>
              {formatMoney(product.price_amount, product.currency)}
            </span>
            {onSale && product.compare_at_price_amount != null ? (
              <span className="text-xs text-gray-400 line-through">
                {formatMoney(product.compare_at_price_amount, product.currency)}
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
