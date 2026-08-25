import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PlanActions } from "@/components/plan-actions";
import { PublishVersionDialog } from "@/components/publish-version-dialog";
import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface PlanVersion {
  id: string;
  version_number: number;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  is_current: boolean;
  published_at: string;
}

interface PlanDetail {
  id: string;
  code: string;
  name: string;
  is_public: boolean;
  trial_days: number;
  grace_period_days: number;
  versions: PlanVersion[];
}

async function getPlan(planId: string): Promise<PlanDetail | null> {
  const response = await serverFetch(`api/v1/platform/plans/${planId}`);
  if (!response.ok) return null;
  return response.json();
}

export default async function PlanDetailPage({
  params,
}: {
  params: Promise<{ locale: string; planId: string }>;
}) {
  const { locale, planId } = await params;
  const t = await getTranslations("platformAdmin.plans");
  const plan = await getPlan(planId);
  if (!plan) notFound();

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/${locale}/plans`} className="text-sm text-muted-foreground hover:underline">
          ← {t("backToList")}
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{plan.name}</h1>
          <p className="text-sm text-muted-foreground">{plan.code}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={plan.is_public ? "success" : "secondary"}>
            {plan.is_public ? t("public") : "—"}
          </Badge>
          <PlanActions planId={plan.id} isPublic={plan.is_public} />
        </div>
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">{t("versions")}</h2>
        <PublishVersionDialog planId={plan.id} />
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30">
            <tr>
              <th className="px-4 py-2 text-start font-medium">#</th>
              <th className="px-4 py-2 text-start font-medium">{t("priceMonthly")}</th>
              <th className="px-4 py-2 text-start font-medium">{t("priceYearly")}</th>
              <th className="px-4 py-2 text-start font-medium">{t("currency")}</th>
              <th className="px-4 py-2 text-start font-medium">{t("current")}</th>
            </tr>
          </thead>
          <tbody>
            {plan.versions.map((version) => (
              <tr key={version.id} className="border-b last:border-0">
                <td className="px-4 py-2">{version.version_number}</td>
                <td className="px-4 py-2">{version.price_monthly}</td>
                <td className="px-4 py-2">{version.price_yearly}</td>
                <td className="px-4 py-2">{version.currency}</td>
                <td className="px-4 py-2">
                  {version.is_current ? <Badge variant="success">{t("current")}</Badge> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
