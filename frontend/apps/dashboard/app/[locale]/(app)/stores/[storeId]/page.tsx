import { Badge } from "@saas/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { OrdersChart } from "@/components/orders-chart";
import { SetupChecklist } from "@/components/setup-checklist";
import { serverFetch } from "@/lib/session";
import { getTranslations } from "next-intl/server";

interface StoreDetail {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
}

interface SubscriptionStatus {
  status: string;
  plan_name: string;
  trial_ends_at: string | null;
  current_period_end: string;
}

interface AnalyticsOverview {
  orders_total: number;
  orders_by_status: Record<string, number>;
  revenue_by_currency: Record<string, number>;
  orders_last_30_days: { date: string; count: number }[];
}

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

const STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
  active: "success",
  trialing: "warning",
  past_due: "destructive",
  canceled: "destructive",
};

export default async function StoreOverviewPage({
  params,
}: {
  params: Promise<{ storeId: string }>;
}) {
  const { storeId } = await params;
  const t = await getTranslations("nav");
  const tAnalytics = await getTranslations("analytics");

  const [storeResponse, subscriptionResponse, analyticsResponse] = await Promise.all([
    serverFetch(`api/v1/dashboard/stores/${storeId}`),
    serverFetch(`api/v1/dashboard/stores/${storeId}/subscription`),
    serverFetch(`api/v1/dashboard/stores/${storeId}/analytics/overview`),
  ]);

  const store: StoreDetail = await storeResponse.json();
  const subscription: SubscriptionStatus | null = subscriptionResponse.ok
    ? await subscriptionResponse.json()
    : null;
  const analytics: AnalyticsOverview | null = analyticsResponse.ok
    ? await analyticsResponse.json()
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{store.name}</h1>
        <p className="text-sm text-muted-foreground">{store.slug}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Store status</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={store.status === "active" ? "success" : "secondary"}>
              {store.status}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">{t("subscription")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {subscription ? (
              <>
                <Badge variant={STATUS_VARIANT[subscription.status] ?? "secondary"}>
                  {subscription.status}
                </Badge>
                <p className="text-sm text-muted-foreground">{subscription.plan_name}</p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Unavailable</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Created</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{new Date(store.created_at).toLocaleDateString()}</p>
          </CardContent>
        </Card>
      </div>

      {analytics ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">
                {tAnalytics("ordersTotal")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{analytics.orders_total}</p>
            </CardContent>
          </Card>

          <Card className="sm:col-span-2">
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">
                {tAnalytics("revenue")}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-4">
              {Object.entries(analytics.revenue_by_currency).length > 0 ? (
                Object.entries(analytics.revenue_by_currency).map(([currency, amount]) => (
                  <p key={currency} className="text-2xl font-semibold">
                    {formatMoney(amount, currency)}
                  </p>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">—</p>
              )}
            </CardContent>
          </Card>

          <Card className="sm:col-span-3">
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">
                {tAnalytics("ordersLast30Days")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <OrdersChart data={analytics.orders_last_30_days} />
            </CardContent>
          </Card>
        </div>
      ) : null}

      <SetupChecklist storeId={storeId} />
    </div>
  );
}
