import { SubscriptionCheckout } from "@/components/subscription-checkout";
import { serverFetch } from "@/lib/session";

interface Me {
  email: string;
  full_name: string;
}

/**
 * Phase E ("product vision reset" -- Subscription Checkout). Reached
 * only from /plans' "Continue to payment" once a plan is selected
 * (checkout_status === ready_for_payment) -- SubscriptionCheckout
 * itself redirects back to /plans if the session isn't in a
 * payment-relevant state, so this page never trusts navigation history
 * alone. `email`/`full_name` are fetched here, server-side, from the
 * authenticated session -- the "customer basic info" the approved spec
 * asks the checkout screen to show, read-only, never re-typed.
 */
export default async function SubscriptionCheckoutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const response = await serverFetch("api/v1/auth/me");
  const me: Me | null = response.ok ? await response.json() : null;

  return (
    <SubscriptionCheckout
      locale={locale}
      email={me?.email ?? ""}
      fullName={me?.full_name ?? ""}
    />
  );
}
