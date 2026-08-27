import { PlanSelector } from "@/components/plan-selector";

/**
 * Phase D ("product vision reset" -- Plan Selection). Authenticated
 * ((app) route group, gated by (app)/layout.tsx exactly like every
 * other dashboard page) -- reached from register-form.tsx/login-
 * form.tsx's post-auth redirect when a `?theme=` (a ThemePreset id)
 * survived from the public marketplace, or by direct navigation if the
 * user already has an in-progress checkout session.
 */
export default async function PlansPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ theme?: string }>;
}) {
  const { locale } = await params;
  const { theme } = await searchParams;

  return <PlanSelector locale={locale} themePresetIdFromUrl={theme ?? null} />;
}
