"use client";

import { Button } from "@saas/ui/button";
import { Select } from "@saas/ui/select";
import { Skeleton } from "@saas/ui/skeleton";
import { Loader2, ShoppingBag } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { formatMoney } from "@/lib/format-money";
import { useCart, useRemoveCartItem, useUpdateCartItem } from "@/lib/hooks/use-cart";

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
        <Button asChild className="mt-6">
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
          return (
            <div key={item.id}>
              <div className="flex items-center gap-4 p-4">
                <div className="flex-1">
                  <p className="text-sm font-medium">{item.variant_sku}</p>
                  <p className="text-sm text-gray-500">
                    {formatMoney(item.unit_price_amount, item.currency)}
                  </p>
                </div>
                <Select
                  className="w-20"
                  value={String(item.quantity)}
                  disabled={isPending}
                  onChange={(e) => {
                    setErrorItemId(null);
                    setPendingItemId(item.id);
                    updateItem.mutate(
                      { itemId: item.id, quantity: Number(e.target.value) },
                      {
                        onError: () => setErrorItemId(item.id),
                        onSettled: () => setPendingItemId(null),
                      }
                    );
                  }}
                >
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setErrorItemId(null);
                    setPendingItemId(item.id);
                    removeItem.mutate(item.id, {
                      onError: () => setErrorItemId(item.id),
                      onSettled: () => setPendingItemId(null),
                    });
                  }}
                  disabled={isPending}
                >
                  {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : t("remove")}
                </Button>
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
