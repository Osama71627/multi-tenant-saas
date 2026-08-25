import { Card } from "@saas/ui/card";
import { getTranslations } from "next-intl/server";

import { OrdersChart } from "@/components/orders-chart";
import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface OverviewMetrics {
  stores_total: number;
  stores_by_status: Record<string, number>;
  plans_total: number;
  subscriptions_by_status: Record<string, number>;
  orders_total: number;
  revenue_by_currency: Record<string, number>;
  orders_last_30_days: { date: string; count: number }[];
}

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

async function getOverview(): Promise<OverviewMetrics | null> {
  const response = await serverFetch("api/v1/platform/overview");
  if (!response.ok) return null;
  return response.json();
}

export default async function OverviewPage() {
  const t = await getTranslations("platformAdmin.overview");
  const tAnalytics = await getTranslations("analytics");
  const metrics = await getOverview();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("title")}</h1>

      {metrics ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">{t("storesTotal")}</p>
              <p className="mt-1 text-2xl font-semibold">{metrics.stores_total}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">{t("plansTotal")}</p>
              <p className="mt-1 text-2xl font-semibold">{metrics.plans_total}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">{tAnalytics("ordersTotal")}</p>
              <p className="mt-1 text-2xl font-semibold">{metrics.orders_total}</p>
            </Card>
          </div>

          <Card className="p-4">
            <p className="mb-2 text-sm font-medium">{tAnalytics("revenue")}</p>
            <div className="flex flex-wrap gap-4">
              {Object.entries(metrics.revenue_by_currency).length > 0 ? (
                Object.entries(metrics.revenue_by_currency).map(([currency, amount]) => (
                  <p key={currency} className="text-2xl font-semibold">
                    {formatMoney(amount, currency)}
                  </p>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">—</p>
              )}
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card className="p-4">
              <p className="mb-2 text-sm font-medium">{t("storesByStatus")}</p>
              <dl className="space-y-1 text-sm">
                {Object.entries(metrics.stores_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <dt className="text-muted-foreground">{status}</dt>
                    <dd className="font-medium">{count}</dd>
                  </div>
                ))}
              </dl>
            </Card>
            <Card className="p-4">
              <p className="mb-2 text-sm font-medium">{t("subscriptionsByStatus")}</p>
              <dl className="space-y-1 text-sm">
                {Object.entries(metrics.subscriptions_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <dt className="text-muted-foreground">{status}</dt>
                    <dd className="font-medium">{count}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>

          <Card className="p-4">
            <p className="mb-2 text-sm font-medium">{tAnalytics("ordersLast30Days")}</p>
            <OrdersChart data={metrics.orders_last_30_days} />
          </Card>
        </>
      ) : null}
    </div>
  );
}
