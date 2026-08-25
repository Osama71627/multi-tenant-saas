"use client";

import { Button } from "@saas/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@saas/ui/dialog";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api-client";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function PromoteSupplierProductDialog({
  storeId,
  supplierProductId,
  suggestedName,
  suggestedPriceAmount,
}: {
  storeId: string;
  supplierProductId: string;
  suggestedName: string;
  suggestedPriceAmount: number;
}) {
  const t = useTranslations("suppliers");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [name, setName] = useState(suggestedName);
  const [slug, setSlug] = useState(slugify(suggestedName));
  const [sku, setSku] = useState("");
  const [priceAmount, setPriceAmount] = useState(String(suggestedPriceAmount));

  async function promote() {
    setPending(true);
    try {
      // Deliberately no `initial_stock` here: without a stock-location
      // picker in this dialog, that field would look functional but be
      // silently ignored by the backend (it only applies stock when a
      // location is also given -- apps/suppliers/services.py). The
      // promoted product lands with zero stock everywhere; the merchant
      // sets it via the existing Inventory page, same as any other
      // manually-created product. Re-add this once a location picker
      // exists here.
      const { error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/supplier-products/{supplier_product_id}/promote",
        {
          params: { path: { store_id: storeId, supplier_product_id: supplierProductId } },
          body: {
            name,
            slug,
            sku,
            price_amount: Number(priceAmount) || 0,
          },
        }
      );
      if (!error) {
        setOpen(false);
        router.refresh();
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">{t("promote")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("promoteTitle")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="promote-name">{t("productName")}</Label>
            <Input
              id="promote-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setSlug(slugify(e.target.value));
              }}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="promote-slug">{t("slug")}</Label>
              <Input id="promote-slug" value={slug} onChange={(e) => setSlug(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="promote-sku">{t("sku")}</Label>
              <Input id="promote-sku" value={sku} onChange={(e) => setSku(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="promote-price">{t("priceAmount")}</Label>
            <Input
              id="promote-price"
              type="number"
              min={0}
              value={priceAmount}
              onChange={(e) => setPriceAmount(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={promote} disabled={pending || !name || !slug || !sku}>
            {t("promote")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
