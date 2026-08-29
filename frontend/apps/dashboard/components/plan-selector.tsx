"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@saas/ui/card";
import { Skeleton } from "@saas/ui/skeleton";
import { Check, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import {
  useCheckoutSession,
  useSelectPlan,
  useStartCheckoutSession,
} from "@/lib/hooks/use-checkout-session";
import { usePublicPlans } from "@/lib/hooks/use-public-plans";
import { usePublicThemePresets } from "@/lib/hooks/use-public-theme-presets";

// Any status past plan-selection -- once a payment attempt exists (or
// business info is next), /subscription/checkout is the single page
// that renders whichever of those states applies (approved Phase E
// spec: one continuous checkout screen, not a route per status).
const PAST_PLAN_SELECTION = new Set([
  "payment_pending",
  "payment_failed",
  "awaiting_business_info",
]);

// `default_settings` is a plain Django JSONField -- drf-spectacular has
// no way to know its shape, so the generated client types it `unknown`
// (same imprecision the marketplace page works around with its own
// hand-written interface). Only the 3 palette fields are read here.
interface ThemePresetPalette {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
}

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

export function PlanSelector({
  locale,
  themePresetIdFromUrl,
}: {
  locale: string;
  themePresetIdFromUrl: string | null;
}) {
  const t = useTranslations("plans");
  const router = useRouter();
  const { data: session, isLoading: sessionLoading } = useCheckoutSession();
  const { data: plans, isLoading: plansLoading } = usePublicPlans();
  const { data: presets } = usePublicThemePresets();
  const startSession = useStartCheckoutSession();
  const selectPlan = useSelectPlan();

  // Attaches the theme from the marketplace/register redirect to the
  // user's session exactly once. A session that already exists (e.g.
  // this page was simply revisited, no ?theme= this time) is left
  // alone -- start_or_update_checkout_session on the backend only
  // updates the theme when a non-null id is actually passed.
  const startedRef = useRef(false);
  useEffect(() => {
    if (themePresetIdFromUrl && !startedRef.current && !sessionLoading) {
      startedRef.current = true;
      startSession.mutate({ theme_preset_id: themePresetIdFromUrl });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire once per mount, not on every session refetch
  }, [themePresetIdFromUrl, sessionLoading]);

  // A session already past plan-selection (payment in flight, failed,
  // or already paid -- e.g. this page was simply revisited) has
  // nothing left to do here -- /subscription/checkout is the single
  // page that renders whichever of those states applies.
  useEffect(() => {
    if (session?.checkout_status && PAST_PLAN_SELECTION.has(session.checkout_status)) {
      router.replace(`/${locale}/subscription/checkout`);
    }
  }, [session?.checkout_status, router, locale]);

  const effectiveThemeId = session?.theme_preset_id ?? themePresetIdFromUrl;

  // No theme picked at all (arrived here directly, with no session and
  // no ?theme=) -- real UX gap found live: this used to show a static
  // "choose a theme first" screen with nothing but a "Browse themes"
  // button, an extra dead click on the way to where the merchant was
  // always going next. Redirect straight there instead, same pattern
  // as the PAST_PLAN_SELECTION redirect above -- this page has nothing
  // useful to render without a theme regardless.
  useEffect(() => {
    if (!sessionLoading && !startSession.isPending && !effectiveThemeId) {
      router.replace(`/${locale}/themes`);
    }
  }, [sessionLoading, startSession.isPending, effectiveThemeId, router, locale]);

  const selectedPreset = presets?.find((p) => p.id === effectiveThemeId);
  const palette = selectedPreset?.default_settings as ThemePresetPalette | undefined;

  if (
    sessionLoading ||
    startSession.isPending ||
    !effectiveThemeId ||
    (session?.checkout_status && PAST_PLAN_SELECTION.has(session.checkout_status))
  ) {
    return (
      <div className="mx-auto max-w-4xl space-y-6 px-4 py-12">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-10 px-4 py-12">
      <div>
        <p className="text-sm font-medium text-muted-foreground">{t("selectedThemeLabel")}</p>
        <Card className="mt-2 flex items-center gap-4 p-4">
          {selectedPreset ? (
            <>
              <div
                className="h-14 w-14 shrink-0 rounded-lg"
                style={{
                  background: `linear-gradient(135deg, ${palette?.primary_color}, ${palette?.secondary_color} 60%, ${palette?.accent_color})`,
                }}
              />
              <div className="flex-1">
                <p className="font-semibold">{selectedPreset.theme_name}</p>
                <p className="text-sm text-muted-foreground">{selectedPreset.theme_category}</p>
              </div>
            </>
          ) : (
            <div className="flex-1 text-sm text-muted-foreground">{t("themeLoading")}</div>
          )}
          <Link
            href={`/${locale}/themes`}
            className="text-sm font-medium text-primary underline underline-offset-4"
          >
            {t("changeTheme")}
          </Link>
        </Card>
      </div>

      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("subtitle")}</p>

        {plansLoading ? (
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-80 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {plans?.map((plan) => {
              const isSelected = session?.plan_version?.id === plan.id;
              const productsQuota = plan.quotas.find((q) => q.quota_key === "products");
              return (
                <Card key={plan.id} className={isSelected ? "ring-2 ring-primary" : undefined}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      {plan.plan_name}
                      {isSelected ? <Badge>{t("selected")}</Badge> : null}
                    </CardTitle>
                    <CardDescription>
                      <span className="text-2xl font-bold text-foreground">
                        {formatMoney(plan.price_monthly, plan.currency)}
                      </span>{" "}
                      {t("perMonth")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-primary" />
                        {productsQuota
                          ? productsQuota.limit === null
                            ? t("unlimitedProducts")
                            : t("productsLimit", { count: productsQuota.limit })
                          : null}
                      </li>
                      {plan.features
                        .filter((f) => f.enabled)
                        .map((f) => (
                          <li key={f.feature_key} className="flex items-center gap-2">
                            <Check className="h-4 w-4 text-primary" />
                            {t(`feature.${f.feature_key}`)}
                          </li>
                        ))}
                    </ul>
                    <Button
                      className="w-full"
                      variant={isSelected ? "secondary" : "default"}
                      disabled={selectPlan.isPending}
                      onClick={() => selectPlan.mutate({ plan_version_id: plan.id })}
                    >
                      {selectPlan.isPending && selectPlan.variables?.plan_version_id === plan.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : isSelected ? (
                        t("selected")
                      ) : (
                        t("selectPlan")
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {session?.checkout_status === "ready_for_payment" ? (
        <div className="flex flex-col items-center gap-3 border-t pt-8 text-center">
          <Button size="lg" onClick={() => router.push(`/${locale}/subscription/checkout`)}>
            {t("continueToPayment")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
