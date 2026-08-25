"use client";

import { Badge } from "@saas/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Skeleton } from "@saas/ui/skeleton";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";

import { useSubscription } from "@/lib/hooks/use-subscription";

const STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
  active: "success",
  trialing: "warning",
  past_due: "destructive",
  canceled: "destructive",
};

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

export default function SubscriptionPage() {
  const t = useTranslations("nav");
  const params = useParams<{ storeId: string }>();
  const { data, isLoading } = useSubscription(params.storeId);

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">{t("subscription")}</h1>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data ? (
        <p className="text-sm text-muted-foreground">Unable to load subscription status.</p>
      ) : (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{data.plan_name}</CardTitle>
              <Badge variant={STATUS_VARIANT[data.status] ?? "secondary"}>{data.status}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Price</span>
              <span>
                {formatMoney(data.price_monthly, data.currency)} / mo ·{" "}
                {formatMoney(data.price_yearly, data.currency)} / yr
              </span>
            </div>
            {data.trial_ends_at ? (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Trial ends</span>
                <span>{new Date(data.trial_ends_at).toLocaleDateString()}</span>
              </div>
            ) : null}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Current period ends</span>
              <span>{new Date(data.current_period_end).toLocaleDateString()}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
