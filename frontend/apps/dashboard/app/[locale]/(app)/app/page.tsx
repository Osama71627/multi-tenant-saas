import { serverFetch } from "@/lib/session";
import { redirect } from "next/navigation";

interface StoreListItem {
  id: string;
  name: string;
  slug: string;
  status: string;
}

/**
 * Landing route for an authenticated merchant with no store context yet
 * -- routes to the first store's overview if they have one, or into the
 * payment-gated plan-selection flow if they don't.
 *
 * Lives at "/[locale]/app" rather than the bare "/[locale]" root as of
 * the Phase A "product vision reset": the root is now the public
 * landing page (../../(public)/page.tsx), so the authenticated
 * dashboard entry point needed its own path. Every post-login/register
 * redirect target was updated alongside this move (login-form.tsx,
 * register-form.tsx) -- see middleware.ts's PUBLIC_PATH_SEGMENTS
 * comment for the other half of this change.
 *
 * Redirects to "/plans", not "/onboarding", as of the post-Phase-D gap
 * fix: a storeless user landing here has, by definition, never paid --
 * routing them into the old free-trial onboarding wizard let ANY
 * authenticated user create a real, fully-provisioned Store (with an
 * auto-attached `trialing` Subscription) with nothing but a name and a
 * slug, completely bypassing Phase D's plan-selection screen and the
 * "no Store before payment" invariant stated throughout the product
 * vision reset -- confirmed live: a user who explicitly selected the
 * paid Professional plan on /plans still ended up with a free store on
 * a mismatched trial plan by simply visiting /onboarding directly
 * instead. /onboarding itself now redirects here too (see that route),
 * and store-switcher.tsx's "create another store" entry was updated to
 * match. This intentionally leaves NO working path to a real Store
 * until Phase E (payment) -> F (business info) -> G (store creation)
 * are built -- by design, not an oversight: that is exactly the
 * invariant this fix restores. Phase G is expected to replace this
 * redirect target with whatever route follows a completed checkout.
 */
export default async function AppIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const response = await serverFetch("api/v1/dashboard/stores");
  const stores: StoreListItem[] = response.ok ? await response.json() : [];
  const [firstStore] = stores;

  if (firstStore) {
    redirect(`/${locale}/stores/${firstStore.id}`);
  }
  redirect(`/${locale}/plans`);
}
