"use client";

import { Button } from "@saas/ui/button";
import { Skeleton } from "@saas/ui/skeleton";
import { Loader2, Minus, Plus, ShoppingBag, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { formatMoney } from "@/lib/format-money";
import { useCart, useRemoveCartItem, useUpdateCartItem } from "@/lib/hooks/use-cart";

/**
 * Real gap found live: a cart line only ever showed the raw
 * `variant_sku` (e.g. "WIDGET-001") -- a shopper recognizes the
 * product NAME, not an internal SKU -- plus a bare quantity `<select>`
 * with no way back to the product itself. Now shows the real product
 * name (linked back to its page), a considered gradient placeholder
 * thumbnail (see components/product-detail.tsx's identical comment on
 * why -- no product-photography pipeline exists in this project), a
 * quantity stepper, and each line's own total, not just the cart-wide
 * subtotal.
 */
export default function CartPage() {
  const { locale } = useParams<{ locale: string }>();
  const t = useTranslations("storefront.cart");
  const { data: cart, isLoading } = useCart();
  const updateItem = useUpdateCartItem();
  const removeItem = useRemoveCartItem();
  // Both mutations are shared across every row -- track which specific
  // item is in flight so only THAT row shows a pending state instead of
  // freezing the whole list on any single quantity change/removal.
  const [pendingItemId, setPendingItemId] = useState<string | null>(null);
  const [errorItemId, setErrorItemId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-3 px-4 py-10">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (!cart?.items.length) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-20 text-center">
        <ShoppingBag className="mx-auto h-10 w-10 text-gray-300" />
        <h1 className="mt-4 text-lg font-semibold">{t("empty")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("emptyDescription")}</p>
        <Button asChild className="mt-6" style={{ backgroundColor: "var(--sf-primary)" }}>
          <Link href={`/${locale}/products`}>{t("continueShopping")}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-semibold">{t("title")}</h1>

      <div className="divide-y rounded-lg border">
        {cart.items.map((item) => {
          const isPending = pendingItemId === item.id;
          const lineTotal = item.unit_price_amount * item.quantity;
          return (
            <div key={item.id}>
              <div className="flex items-center gap-4 p-4">
                <Link
                  href={`/${locale}/products/${item.product_slug}`}
                  className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-md"
                  style={{
                    background:
                      "linear-gradient(160deg, color-mix(in srgb, var(--sf-secondary, #ccc) 18%, white), color-mix(in srgb, var(--sf-accent, #999) 22%, white))",
                  }}
                >
                  <span
                    className="text-2xl font-bold opacity-25"
                    style={{ color: "var(--sf-primary)" }}
                    aria-hidden
                  >
                    {item.product_name.charAt(0).toUpperCase()}
                  </span>
                </Link>

                <div className="min-w-0 flex-1">
                  <Link
                    href={`/${locale}/products/${item.product_slug}`}
                    className="block truncate text-sm font-medium hover:underline"
                  >
                    {item.product_name}
                  </Link>
                  <p className="mt-0.5 text-xs text-gray-400">{item.variant_sku}</p>
                  <p className="mt-1 text-sm text-gray-600">
                    {formatMoney(item.unit_price_amount, item.currency)}
                  </p>
                </div>

                <div className="flex items-center rounded-md border">
                  <button
                    type="button"
                    aria-label={t("decreaseQuantity")}
                    disabled={isPending}
                    onClick={() => {
                      setErrorItemId(null);
                      setPendingItemId(item.id);
                      updateItem.mutate(
                        { itemId: item.id, quantity: Math.max(1, item.quantity - 1) },
                        {
                          onError: () => setErrorItemId(item.id),
                          onSettled: () => setPendingItemId(null),
                        }
                      );
                    }}
                    className="p-2 text-gray-600 hover:text-black disabled:opacity-30"
                  >
                    <Minus className="h-3 w-3" />
                  </button>
                  <span className="w-6 text-center text-sm font-medium">{item.quantity}</span>
                  <button
                    type="button"
                    aria-label={t("increaseQuantity")}
                    disabled={isPending || item.quantity >= 10}
                    onClick={() => {
                      setErrorItemId(null);
                      setPendingItemId(item.id);
                      updateItem.mutate(
                        { itemId: item.id, quantity: item.quantity + 1 },
                        {
                          onError: () => setErrorItemId(item.id),
                          onSettled: () => setPendingItemId(null),
                        }
                      );
                    }}
                    className="p-2 text-gray-600 hover:text-black disabled:opacity-30"
                  >
                    <Plus className="h-3 w-3" />
                  </button>
                </div>

                <p className="w-20 shrink-0 text-end text-sm font-semibold">
                  {formatMoney(lineTotal, item.currency)}
                </p>

                <button
                  type="button"
                  aria-label={t("remove")}
                  disabled={isPending}
                  onClick={() => {
                    setErrorItemId(null);
                    setPendingItemId(item.id);
                    removeItem.mutate(item.id, {
                      onError: () => setErrorItemId(item.id),
                      onSettled: () => setPendingItemId(null),
                    });
                  }}
                  className="shrink-0 p-1.5 text-gray-400 hover:text-red-600 disabled:opacity-30"
                >
                  {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
                </button>
              </div>
              {errorItemId === item.id ? (
                <p className="px-4 pb-3 text-sm text-red-600">{t("updateError")}</p>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex items-center justify-between border-t pt-4">
        <span className="text-sm text-gray-600">{t("subtotal")}</span>
        <span className="text-lg font-semibold">
          {formatMoney(cart.subtotal_amount, cart.currency)}
        </span>
      </div>

      <Button asChild className="mt-6 w-full" style={{ backgroundColor: "var(--sf-primary)" }}>
        <Link href={`/${locale}/checkout`}>{t("checkout")}</Link>
      </Button>
    </div>
  );
}
