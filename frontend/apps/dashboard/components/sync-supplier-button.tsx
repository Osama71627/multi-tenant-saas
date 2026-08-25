"use client";

import { Button } from "@saas/ui/button";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api-client";

export function SyncSupplierButton({ storeId, supplierId }: { storeId: string; supplierId: string }) {
  const t = useTranslations("suppliers");
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function sync() {
    setPending(true);
    try {
      await api.POST("/api/v1/dashboard/stores/{store_id}/suppliers/{supplier_id}/sync", {
        params: { path: { store_id: storeId, supplier_id: supplierId } },
      });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <Button size="sm" variant="outline" onClick={sync} disabled={pending}>
      <RefreshCw className={pending ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
      {pending ? t("syncing") : t("sync")}
    </Button>
  );
}
