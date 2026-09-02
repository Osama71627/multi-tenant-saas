import Link from "next/link";

import type { HomestoreProductListItem } from "./types";

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

/**
 * Rounded card, square photo area, a percentage-off badge, a
 * bordered-card retail convention. Real photo when `image_url` is set
 * (fixture-only -- see HomestoreProductListItem.image_url's own
 * comment), a considered gradient + large initial otherwise -- the
 * same placeholder treatment every other theme's own ProductCard
 * uses, never a flat gray box with tiny text.
 */
export function HomestoreProductCard({
  product,
  href,
}: {
  product: HomestoreProductListItem;
  href: string;
}) {
  const onSale =
    product.compare_at_price_amount != null &&
    product.price_amount != null &&
    product.compare_at_price_amount > product.price_amount;
  const discountPct =
    onSale && product.compare_at_price_amount
      ? Math.round(
          (1 - (product.price_amount as number) / product.compare_at_price_amount) * 100
        )
      : null;

  return (
    <Link
      href={href}
      className="group block overflow-hidden rounded-2xl border border-neutral-100 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl"
    >
      <div className="relative aspect-square overflow-hidden bg-neutral-100">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_url}
            alt={product.name}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
        ) : (
          <div
            className="flex h-full w-full items-center justify-center transition-transform duration-500 group-hover:scale-110"
            style={{
              background:
                "linear-gradient(160deg, color-mix(in srgb, var(--sf-secondary) 16%, white), color-mix(in srgb, var(--sf-accent) 20%, white))",
            }}
          >
            <span
              className="text-6xl font-bold opacity-20"
              style={{ color: "var(--sf-primary)" }}
              aria-hidden
            >
              {product.name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        {discountPct ? (
          <span className="absolute start-3 top-3 rounded-full bg-red-500 px-3 py-1 text-xs font-bold text-white">
            -{discountPct}%
          </span>
        ) : null}
      </div>
      <div className="p-4">
        <p className="truncate text-sm font-semibold text-neutral-900 md:text-base">
          {product.name}
        </p>
        {product.price_amount != null && product.currency ? (
          <p className="mt-1.5 flex items-center gap-2">
            <span className="text-lg font-bold text-neutral-900">
              {formatMoney(product.price_amount, product.currency)}
            </span>
            {onSale && product.compare_at_price_amount != null ? (
              <span className="text-sm text-neutral-400 line-through">
                {formatMoney(product.compare_at_price_amount, product.currency)}
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
