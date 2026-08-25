import { getCurrentUser } from "@/lib/session";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Defense in depth beyond middleware.ts's cookie-presence check: this
 * actually calls GET /auth/me server-side. A present-but-expired/invalid
 * access token cookie passes the middleware's shallow check but fails
 * here, bouncing to /login for real -- Django stays the sole source of
 * truth for "is this session actually valid", never just "is there a
 * cookie".
 */
export default async function AppLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const user = await getCurrentUser();
  if (!user) redirect(`/${locale}/login`);

  return children;
}
