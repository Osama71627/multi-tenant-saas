import Link from "next/link";

import type { FashionProductListItem } from "./types";

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

/**
 * Portrait (3:4) catalog-style card with a corner ribbon -- the
 * fashion-retail convention (tall product photography, a small "New"/
 * "Sale" flag), structurally different from Aurora's plain square card
 * with no badge at all.
 *
 * No product-photography pipeline exists in this project -- the
 * placeholder used to be a flat gray box with the product name in tiny
 * text, which read as broken rather than deliberate. A soft tint of
 * the theme's own secondary/accent colours plus a large serif initial
 * is the "considered placeholder" treatment instead -- still honestly
 * "no photo", but looks like a designed empty state, not an error.
 */
export function FashionProductCard({
  product,
  href,
}: {
  product: FashionProductListItem;
  href: string;
}) {
  const onSale =
    product.compare_at_price_amount != null &&
    product.price_amount != null &&
    product.compare_at_price_amount > product.price_amount;

  return (
    <Link href={href} className="group block">
      <div
        className="relative aspect-[3/4] overflow-hidden"
        style={{
          background: "linear-gradient(160deg, color-mix(in srgb, var(--sf-secondary) 18%, white), color-mix(in srgb, var(--sf-accent) 22%, white))",
        }}
      >
        <div className="flex h-full items-center justify-center transition-transform duration-500 ease-out group-hover:scale-105">
          <span
            className="font-serif text-6xl opacity-25"
            style={{ color: "var(--sf-primary)" }}
            aria-hidden
          >
            {product.name.charAt(0).toUpperCase()}
          </span>
        </div>
        <span
          className="absolute start-3 top-3 rounded-full px-3 py-1 text-[10px] font-medium uppercase tracking-widest text-white shadow-sm"
          style={{ backgroundColor: onSale ? "var(--sf-accent)" : "var(--sf-primary)" }}
        >
          {onSale ? "Sale" : "New"}
        </span>
      </div>
      <div className="mt-3 space-y-1 text-center">
        <p className="truncate font-serif text-sm underline-offset-4 group-hover:underline">
          {product.name}
        </p>
        {product.price_amount != null && product.currency ? (
          <p className="flex items-center justify-center gap-2 text-sm">
            <span className="font-medium">{formatMoney(product.price_amount, product.currency)}</span>
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
