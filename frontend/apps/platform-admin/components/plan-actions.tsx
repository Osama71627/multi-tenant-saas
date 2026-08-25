"use client";

import { Button } from "@saas/ui/button";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api-client";

export function PlanActions({ planId, isPublic }: { planId: string; isPublic: boolean }) {
  const t = useTranslations("platformAdmin.plans");
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function toggle() {
    setPending(true);
    try {
      const path = isPublic
        ? ("/api/v1/platform/plans/{plan_id}/deactivate" as const)
        : ("/api/v1/platform/plans/{plan_id}/activate" as const);
      await api.POST(path, { params: { path: { plan_id: planId } } });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <Button size="sm" variant={isPublic ? "outline" : "default"} onClick={toggle} disabled={pending}>
      {isPublic ? t("deactivate") : t("activate")}
    </Button>
  );
}
