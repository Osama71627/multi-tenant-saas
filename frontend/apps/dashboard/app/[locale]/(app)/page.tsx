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
 * onboarding wizard if they don't. Matches the approved merchant
 * journey (Discover -> Preview -> Choose -> Configure -> Provision ->
 * Launch -> Manage): a brand-new merchant never sees a blank dashboard,
 * they land straight in onboarding.
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
  redirect(`/${locale}/onboarding`);
}
