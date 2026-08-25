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

export function StoreActions({ storeId, status }: { storeId: string; status: string }) {
  const t = useTranslations("platformAdmin.stores");
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [open, setOpen] = useState(false);

  async function suspend() {
    setPending(true);
    try {
      await api.POST("/api/v1/platform/stores/{store_id}/suspend", {
        params: { path: { store_id: storeId } },
        body: { reason },
      });
      setOpen(false);
      setReason("");
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  async function activate() {
    setPending(true);
    try {
      await api.POST("/api/v1/platform/stores/{store_id}/activate", {
        params: { path: { store_id: storeId } },
      });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  if (status === "suspended") {
    return (
      <Button size="sm" variant="outline" onClick={activate} disabled={pending}>
        {t("activate")}
      </Button>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="destructive">
          {t("suspend")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("confirmSuspend")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="reason">{t("suspendReason")}</Label>
          <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <DialogFooter>
          <Button variant="destructive" onClick={suspend} disabled={pending}>
            {t("suspend")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
