import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";

import { SubscriptionActions } from "@/components/subscription-actions";
import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface Subscription {
  id: string;
  store_id: string;
  status: string;
  billing_interval: string;
  plan_code: string;
  plan_version_number: number;
  current_period_end: string;
}

async function getSubscriptions(storeId?: string): Promise<Subscription[]> {
  const query = storeId ? `?store_id=${encodeURIComponent(storeId)}` : "";
  const response = await serverFetch(`api/v1/platform/subscriptions${query}`);
  if (!response.ok) return [];
  return response.json();
}

function statusVariant(status: string): "success" | "destructive" | "warning" | "secondary" {
  if (status === "active") return "success";
  if (status === "canceled") return "destructive";
  if (status === "past_due") return "warning";
  return "secondary";
}

export default async function SubscriptionsPage({
  searchParams,
}: {
  searchParams: Promise<{ store_id?: string }>;
}) {
  const { store_id } = await searchParams;
  const t = await getTranslations("platformAdmin.subscriptions");
  const subscriptions = await getSubscriptions(store_id);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("title")}</h1>

      {subscriptions.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("store")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("plan")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("status")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("periodEnd")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {subscriptions.map((subscription) => (
                <tr key={subscription.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                    {subscription.store_id}
                  </td>
                  <td className="px-4 py-2">
                    {subscription.plan_code} v{subscription.plan_version_number}
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={statusVariant(subscription.status)}>
                      {subscription.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(subscription.current_period_end).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2">
                    <SubscriptionActions
                      subscriptionId={subscription.id}
                      status={subscription.status}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
