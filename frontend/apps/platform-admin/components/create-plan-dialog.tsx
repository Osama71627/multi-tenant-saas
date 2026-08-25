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
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api-client";

export function CreatePlanDialog() {
  const t = useTranslations("platformAdmin.plans");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [trialDays, setTrialDays] = useState("0");
  const [gracePeriodDays, setGracePeriodDays] = useState("3");

  async function create() {
    setPending(true);
    try {
      const { error } = await api.POST("/api/v1/platform/plans", {
        body: {
          code,
          name,
          is_public: true,
          trial_days: Number(trialDays) || 0,
          grace_period_days: Number(gracePeriodDays) || 3,
        },
      });
      if (!error) {
        setOpen(false);
        setCode("");
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
            <Label htmlFor="code">{t("code")}</Label>
            <Input id="code" value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">{t("name")}</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="trialDays">{t("trialDays")}</Label>
              <Input
                id="trialDays"
                type="number"
                min={0}
                value={trialDays}
                onChange={(e) => setTrialDays(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gracePeriodDays">{t("gracePeriodDays")}</Label>
              <Input
                id="gracePeriodDays"
                type="number"
                min={0}
                value={gracePeriodDays}
                onChange={(e) => setGracePeriodDays(e.target.value)}
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={create} disabled={pending || !code || !name}>
            {t("create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
