import { redirect } from "next/navigation";

/**
 * Retired as a live entry point (post-Phase-D gap fix): this used to be
 * the free-trial store-creation wizard (OnboardingWizard,
 * components/onboarding-wizard.tsx) -- reachable by any authenticated
 * storeless user via "/[locale]/app"'s redirect, and by any existing
 * merchant via store-switcher.tsx's "create another store" entry. Both
 * let a Store get created (with an auto-attached `trialing`
 * Subscription) with just a name and a slug, no plan selection and no
 * payment -- bypassing the "no Store before payment" invariant Phase D
 * built /plans to enforce.
 *
 * This route now only redirects, so a stale bookmark or link still
 * lands somewhere useful rather than 404ing. The wizard component
 * itself is left in place, unused, as reference for Phase G (real
 * store creation after a completed checkout) rather than deleted --
 * see "/[locale]/app"'s page.tsx docstring for the full rationale.
 */
export default async function OnboardingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect(`/${locale}/plans`);
}
