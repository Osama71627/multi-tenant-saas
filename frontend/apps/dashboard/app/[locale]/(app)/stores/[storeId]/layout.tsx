import { DashboardShell } from "@/components/dashboard-shell";
import { getCurrentUser, serverFetch } from "@/lib/session";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Verifies the store exists AND the current user can see it before
 * rendering any store-scoped page under it -- Django is the real
 * authority (404 vs 403 semantics live entirely in
 * backend/apps/stores/mixins.py:StoreScopedAPIView); this layout does
 * not duplicate that logic, it just refuses to render the shell around
 * a store the API itself won't return.
 */
export default async function StoreLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string; storeId: string }>;
}) {
  const { locale, storeId } = await params;

  const [storeResponse, user] = await Promise.all([
    serverFetch(`api/v1/dashboard/stores/${storeId}`),
    getCurrentUser(),
  ]);

  if (!storeResponse.ok) notFound();
  if (!user) notFound();

  return (
    <DashboardShell locale={locale} storeId={storeId} userEmail={user.email}>
      {children}
    </DashboardShell>
  );
}
