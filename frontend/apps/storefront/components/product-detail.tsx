"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Check, Minus, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useAvailability } from "@/lib/hooks/use-availability";
import { useAddToCart } from "@/lib/hooks/use-cart";
import { formatMoney } from "@/lib/format-money";
import type { StorefrontProductDetail } from "@/lib/catalog";

function variantMatchesSelection(
  variant: StorefrontProductDetail["variants"][number],
  selection: Record<string, string>
): boolean {
  return Object.entries(selection).every(([optionName, value]) =>
    variant.option_values.some((ov) => ov.option_name === optionName && ov.value === value)
  );
}

/**
 * Real gap found live: this used to be a single narrow column (image-
 * less, no visual weight at all) even on a wide desktop viewport, with
 * a bare `<select>` for options and another `<select>` just for
 * quantity. Redesigned around a real two-column layout (image left,
 * details right, on `sm:` and up) matching every real e-commerce PDP
 * convention, swatch-style option buttons instead of a dropdown
 * (nothing is hidden behind a click to see what's even available), and
 * a proper quantity stepper. No product-photography pipeline exists in
 * this project (same honest constraint documented on
 * @saas/theme-fashion's FashionProductCard) -- the image slot is a
 * considered gradient placeholder using the store's own theme colours,
 * not a broken-looking gray box.
 */
export function ProductDetail({ product }: { product: StorefrontProductDetail }) {
  const t = useTranslations("storefront.product");
  const options = product.options;
  const variants = product.variants;

  const [selection, setSelection] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      options.map((option) => [option.name, option.values[0]?.value ?? ""])
    )
  );

  const selectedVariant = useMemo(() => {
    if (!options.length) return variants[0];
    return variants.find((v) => variantMatchesSelection(v, selection)) ?? variants[0];
  }, [options.length, variants, selection]);

  const { data: availability } = useAvailability(variants.map((v) => v.id));
  const available = selectedVariant ? (availability?.[selectedVariant.id] ?? null) : null;
  const inStock = available === null || available > 0;
  const maxQuantity = Math.max(1, Math.min(10, available ?? 10));

  const [quantity, setQuantity] = useState(1);
  useEffect(() => {
    // A variant switch can lower the available quantity below whatever
    // was previously selected -- keep the picker honest rather than
    // silently letting a stale, now-too-high quantity through.
    setQuantity((q) => Math.min(q, maxQuantity));
  }, [maxQuantity]);

  const addToCart = useAddToCart();
  const [justAdded, setJustAdded] = useState(false);
  useEffect(() => {
    if (!justAdded) return;
    const timeout = setTimeout(() => setJustAdded(false), 2500);
    return () => clearTimeout(timeout);
  }, [justAdded]);

  const onSale =
    selectedVariant?.compare_at_price_amount != null &&
    selectedVariant.compare_at_price_amount > selectedVariant.price_amount;

  return (
    <div className="grid gap-10 sm:grid-cols-2">
      <div
        className="relative flex aspect-square items-center justify-center overflow-hidden rounded-lg"
        style={{
          background:
            "linear-gradient(160deg, color-mix(in srgb, var(--sf-secondary, #ccc) 18%, white), color-mix(in srgb, var(--sf-accent, #999) 22%, white))",
        }}
      >
        <span
          className="text-8xl font-bold opacity-20"
          style={{ color: "var(--sf-primary)" }}
          aria-hidden
        >
          {product.name.charAt(0).toUpperCase()}
        </span>
      </div>

      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">{product.name}</h1>
          {selectedVariant ? (
            <p className="mt-2 flex items-center gap-2 text-xl font-semibold">
              <span style={{ color: "var(--sf-primary)" }}>
                {formatMoney(selectedVariant.price_amount, selectedVariant.currency)}
              </span>
              {onSale && selectedVariant.compare_at_price_amount != null ? (
                <span className="text-base font-normal text-gray-400 line-through">
                  {formatMoney(selectedVariant.compare_at_price_amount, selectedVariant.currency)}
                </span>
              ) : null}
            </p>
          ) : null}
          <div className="mt-3">
            <Badge variant={inStock ? "success" : "secondary"}>
              {inStock ? t("inStock") : t("outOfStock")}
            </Badge>
          </div>
        </div>

        {options.map((option) => (
          <div key={option.id} className="space-y-2">
            <p className="text-sm font-medium">{option.name}</p>
            <div className="flex flex-wrap gap-2">
              {option.values.map((value) => {
                const isSelected = selection[option.name] === value.value;
                return (
                  <button
                    key={value.id}
                    type="button"
                    onClick={() =>
                      setSelection((prev) => ({ ...prev, [option.name]: value.value }))
                    }
                    className="rounded-md border px-4 py-2 text-sm font-medium transition-colors"
                    style={
                      isSelected
                        ? {
                            borderColor: "var(--sf-primary)",
                            backgroundColor: "var(--sf-primary)",
                            color: "white",
                          }
                        : { borderColor: "#e5e7eb" }
                    }
                  >
                    {value.value}
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {product.description ? (
          <div>
            <h2 className="text-sm font-medium text-gray-700">{t("description")}</h2>
            <p className="mt-1 whitespace-pre-line text-sm text-gray-600">{product.description}</p>
          </div>
        ) : null}

        <div className="space-y-3 border-t pt-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center rounded-md border">
              <button
                type="button"
                aria-label={t("decreaseQuantity")}
                disabled={!inStock || quantity <= 1}
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="p-2.5 text-gray-600 hover:text-black disabled:opacity-30"
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
              <span className="w-8 text-center text-sm font-medium">{quantity}</span>
              <button
                type="button"
                aria-label={t("increaseQuantity")}
                disabled={!inStock || quantity >= maxQuantity}
                onClick={() => setQuantity((q) => Math.min(maxQuantity, q + 1))}
                className="p-2.5 text-gray-600 hover:text-black disabled:opacity-30"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
            <Button
              className="flex-1"
              disabled={!selectedVariant || !inStock || addToCart.isPending}
              onClick={() => {
                if (!selectedVariant) return;
                addToCart.mutate(
                  { variant: selectedVariant.id, quantity },
                  { onSuccess: () => setJustAdded(true) }
                );
              }}
              style={{ backgroundColor: "var(--sf-primary)" }}
            >
              {addToCart.isPending ? t("adding") : t("addToCart")}
            </Button>
          </div>
          {justAdded ? (
            <span className="flex items-center gap-1 text-sm font-medium text-emerald-600">
              <Check className="h-4 w-4" />
              {t("added")}
            </span>
          ) : null}
          {addToCart.isError ? (
            <p className="text-sm text-red-600">
              {(addToCart.error as { detail?: string })?.detail ?? "Could not add to cart."}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
