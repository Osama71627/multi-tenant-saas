import { getCurrentPlatformStaffUser } from "@/lib/session";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AdminShell } from "@/components/admin-shell";

// Every page under this layout is auth-gated, per-request data (store
// list, plans, subscriptions, users, audit logs) -- `cookies()` inside
// `serverFetch` should already opt this subtree into dynamic rendering,
// but `next build` still prerendered these as SSG in practice (same
// class of issue hit and fixed for the storefront app's Host-dependent
// pages this project -- see that app's `[locale]/layout.tsx`). Explicit
// beats implicit here: never serve a stale, build-time-frozen snapshot
// of privileged cross-tenant data.
export const dynamic = "force-dynamic";

/**
 * Defense in depth beyond middleware.ts's cookie-presence check: calls
 * GET /auth/me server-side AND requires `is_platform_staff` -- a
 * merchant with a perfectly valid dashboard session gets redirected to
 * /login here too, same as someone with no session at all. Django's
 * `IsPlatformStaff` permission on every /api/v1/platform/* endpoint is
 * still the real, authoritative boundary; this only keeps a non-staff
 * user from ever seeing the admin shell/nav in the first place.
 */
export default async function AppLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const user = await getCurrentPlatformStaffUser();
  if (!user) redirect(`/${locale}/login`);

  return (
    <AdminShell locale={locale} userEmail={user.email}>
      {children}
    </AdminShell>
  );
}
