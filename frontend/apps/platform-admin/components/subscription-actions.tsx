"use client";

import { Button } from "@saas/ui/button";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api-client";

export function SubscriptionActions({
  subscriptionId,
  status,
}: {
  subscriptionId: string;
  status: string;
}) {
  const t = useTranslations("platformAdmin.subscriptions");
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function run(action: "activate" | "cancel") {
    setPending(true);
    try {
      const path =
        action === "activate"
          ? ("/api/v1/platform/subscriptions/{subscription_id}/activate" as const)
          : ("/api/v1/platform/subscriptions/{subscription_id}/cancel" as const);
      await api.POST(path, { params: { path: { subscription_id: subscriptionId } } });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  if (status === "canceled") return null;

  return (
    <div className="flex justify-end gap-2">
      {status !== "active" ? (
        <Button size="sm" variant="outline" onClick={() => run("activate")} disabled={pending}>
          {t("activate")}
        </Button>
      ) : null}
      <Button size="sm" variant="destructive" onClick={() => run("cancel")} disabled={pending}>
        {t("cancel")}
      </Button>
    </div>
  );
}
