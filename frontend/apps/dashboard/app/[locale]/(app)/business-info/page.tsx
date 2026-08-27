import { BusinessInfoForm } from "@/components/business-info-form";
import { serverFetch } from "@/lib/session";

interface Me {
  email: string;
}

/**
 * Phase F ("product vision reset"). Reached only after a successful
 * Phase E demo payment (BusinessInfoForm itself redirects back to
 * /plans if the checkout session isn't in awaiting_business_info --
 * this page never trusts navigation history alone). `contact_email` is
 * fetched here, server-side, from the authenticated session -- shown
 * read-only, never re-typed, and never sent back to the server as part
 * of the form submission (the backend always uses request.user.email
 * regardless of what a client sends).
 */
export default async function BusinessInfoPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const response = await serverFetch("api/v1/auth/me");
  const me: Me | null = response.ok ? await response.json() : null;

  return <BusinessInfoForm locale={locale} email={me?.email ?? ""} />;
}
