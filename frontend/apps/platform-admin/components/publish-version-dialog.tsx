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

export function PublishVersionDialog({ planId }: { planId: string }) {
  const t = useTranslations("platformAdmin.plans");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [priceMonthly, setPriceMonthly] = useState("0");
  const [priceYearly, setPriceYearly] = useState("0");
  const [currency, setCurrency] = useState("SAR");

  async function publish() {
    setPending(true);
    try {
      const { error } = await api.POST("/api/v1/platform/plans/{plan_id}/versions", {
        params: { path: { plan_id: planId } },
        body: {
          price_monthly: Number(priceMonthly) || 0,
          price_yearly: Number(priceYearly) || 0,
          currency,
          make_current: true,
        },
      });
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
        <Button size="sm" variant="outline">
          {t("publishVersion")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("publishVersion")}</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="priceMonthly">{t("priceMonthly")}</Label>
            <Input
              id="priceMonthly"
              type="number"
              min={0}
              value={priceMonthly}
              onChange={(e) => setPriceMonthly(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="priceYearly">{t("priceYearly")}</Label>
            <Input
              id="priceYearly"
              type="number"
              min={0}
              value={priceYearly}
              onChange={(e) => setPriceYearly(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="currency">{t("currency")}</Label>
            <Input
              id="currency"
              maxLength={3}
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={publish} disabled={pending}>
            {t("publishVersion")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
