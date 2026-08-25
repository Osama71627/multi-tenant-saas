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
import { Select } from "@saas/ui/select";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api-client";

export function CreateSupplierDialog({ storeId }: { storeId: string }) {
  const t = useTranslations("suppliers");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState("markup_percent");
  const [value, setValue] = useState("50");
  const [minProfit, setMinProfit] = useState("0");

  async function create() {
    setPending(true);
    try {
      const { error } = await api.POST("/api/v1/dashboard/stores/{store_id}/suppliers", {
        params: { path: { store_id: storeId } },
        body: {
          name,
          provider: "mock",
          is_active: true,
          pricing_strategy: strategy as never,
          pricing_value: Number(value) || 0,
          min_profit_amount: Number(minProfit) || 0,
        },
      });
      if (!error) {
        setOpen(false);
        setName("");
        router.refresh();
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="h-4 w-4" />
          {t("create")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("createTitle")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="supplier-name">{t("name")}</Label>
            <Input id="supplier-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="pricing-strategy">{t("pricingStrategy")}</Label>
              <Select
                id="pricing-strategy"
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
              >
                <option value="markup_percent">{t("markupPercent")}</option>
                <option value="margin_percent">{t("marginPercent")}</option>
                <option value="fixed">{t("fixed")}</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pricing-value">{t("pricingValue")}</Label>
              <Input
                id="pricing-value"
                type="number"
                min={0}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="min-profit">{t("minProfitAmount")}</Label>
            <Input
              id="min-profit"
              type="number"
              min={0}
              value={minProfit}
              onChange={(e) => setMinProfit(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={create} disabled={pending || !name}>
            {t("create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
