import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { CreatePlanDialog } from "@/components/create-plan-dialog";
import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface Plan {
  id: string;
  code: string;
  name: string;
  is_public: boolean;
  trial_days: number;
  grace_period_days: number;
  is_default_trial: boolean;
  created_at: string;
}

async function getPlans(): Promise<Plan[]> {
  const response = await serverFetch("api/v1/platform/plans");
  if (!response.ok) return [];
  return response.json();
}

export default async function PlansPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations("platformAdmin.plans");
  const plans = await getPlans();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <CreatePlanDialog />
      </div>

      {plans.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("code")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("name")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("public")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("trialDays")}</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => (
                <tr key={plan.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">
                    <Link href={`/${locale}/plans/${plan.id}`} className="hover:underline">
                      {plan.code}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{plan.name}</td>
                  <td className="px-4 py-2">
                    <Badge variant={plan.is_public ? "success" : "secondary"}>
                      {plan.is_public ? t("public") : "—"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">{plan.trial_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
