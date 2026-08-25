"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Select } from "@saas/ui/select";
import { Check } from "lucide-react";
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{product.name}</h1>
        {selectedVariant ? (
          <p className="mt-2 text-xl font-semibold" style={{ color: "var(--sf-primary)" }}>
            {formatMoney(selectedVariant.price_amount, selectedVariant.currency)}
          </p>
        ) : null}
      </div>

      {options.map((option) => (
        <div key={option.id} className="space-y-1.5">
          <label className="text-sm font-medium">{option.name}</label>
          <Select
            value={selection[option.name] ?? ""}
            onChange={(e) => setSelection((prev) => ({ ...prev, [option.name]: e.target.value }))}
          >
            {option.values.map((value) => (
              <option key={value.id} value={value.value}>
                {value.value}
              </option>
            ))}
          </Select>
        </div>
      ))}

      <div>
        <Badge variant={inStock ? "success" : "secondary"}>
          {inStock ? t("inStock") : t("outOfStock")}
        </Badge>
      </div>

      {product.description ? (
        <div>
          <h2 className="text-sm font-medium text-gray-700">{t("description")}</h2>
          <p className="mt-1 whitespace-pre-line text-sm text-gray-600">{product.description}</p>
        </div>
      ) : null}

      <div className="flex items-center gap-3">
        <Select
          className="w-20"
          value={String(quantity)}
          disabled={!inStock}
          onChange={(e) => setQuantity(Number(e.target.value))}
        >
          {Array.from({ length: maxQuantity }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </Select>
        <Button
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
        {justAdded ? (
          <span className="flex items-center gap-1 text-sm font-medium text-emerald-600">
            <Check className="h-4 w-4" />
            {t("added")}
          </span>
        ) : null}
      </div>
      {addToCart.isError ? (
        <p className="text-sm text-red-600">
          {(addToCart.error as { detail?: string })?.detail ?? "Could not add to cart."}
        </p>
      ) : null}
    </div>
  );
}
