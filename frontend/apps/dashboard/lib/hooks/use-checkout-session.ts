"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

const QUERY_KEY = ["checkout-session"];

/** Phase D: the authenticated user's own in-progress checkout session,
 * always resolved server-side by identity (never a client-held session
 * id) -- see backend/apps/subscriptions/models.py's
 * SubscriptionCheckoutSession docstring for why. A 404 means "nothing
 * started yet", not an error -- surfaced as `data: undefined`, not a
 * thrown/query-error state, so the plan-selection page doesn't need to
 * special-case a 404 vs. a genuine failure. */
export function useCheckoutSession(options?: { pollWhilePaymentPending?: boolean }) {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/subscriptions/checkout-sessions/current");
      if (response.status === 404) return null;
      if (error) throw error;
      return data;
    },
    // Phase E: while a demo payment is in flight, poll this SAME query
    // (not a separate one) until the webhook-driven backend state
    // moves it off payment_pending -- reading `checkout_status` off
    // THIS query's own cached data, not a second query's, is what
    // keeps the poll condition and the data it reacts to perfectly in
    // sync (a real bug found live-testing this: coordinating two
    // separate queries -- this one plus a payment-intent query -- left
    // a window where the poll condition read stale/undefined data from
    // the OTHER query and never started polling at all, even though
    // the backend had already resolved the payment in ~100ms).
    refetchInterval: (query) => {
      if (!options?.pollWhilePaymentPending) return false;
      return query.state.data?.checkout_status === "payment_pending" ? 1000 : false;
    },
    // TanStack Query pauses `refetchInterval` while the tab/window
    // isn't focused by default -- wrong for a payment-status screen
    // specifically: a real merchant plausibly alt-tabs away mid-
    // payment (checking email, switching to their card app for a 3DS
    // code, ...) and the poll must keep running so the page is already
    // resolved when they come back, not stuck showing "Processing…"
    // until they click back into the tab. Also what made this
    // invisible testing live in an automated, backgrounded browser tab
    // -- polling never fired at all without this.
    refetchIntervalInBackground: true,
  });
}

/** Starts a session (or updates the theme on the existing active one --
 * upsert, per the backend's own uniq_active_checkout_session_per_user
 * constraint). Called once when the plan-selection page loads with a
 * `?theme=` param. */
export function useStartCheckoutSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { theme_preset_id?: string }) => {
      const { data, error } = await api.POST("/api/v1/subscriptions/checkout-sessions/current", {
        body: input,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
    },
  });
}

/** Selects a plan on the existing session -- server-validated against
 * real Plan/PlanVersion data (apps.subscriptions.services.
 * select_plan_for_checkout_session); the request only ever carries a
 * plan_version_id, never a price. */
export function useSelectPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { plan_version_id: string }) => {
      const { data, error } = await api.PATCH("/api/v1/subscriptions/checkout-sessions/current", {
        body: input,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
    },
  });
}

/** Phase E: starts (or retries) a real sandbox-provider-backed payment
 * attempt. `card_number` is only ever used server-side to pick a demo
 * outcome (apps.subscriptions.billing.simulate_demo_outcome) -- never
 * persisted, never influences price (server-derived from PlanVersion
 * regardless of anything this call sends). Gated by
 * SUBSCRIPTION_BILLING_MODE -- a 503 means subscription checkout is
 * disabled in this environment (production, always, until a real
 * provider exists). The intent resolves ASYNCHRONOUSLY (a Celery task
 * simulating the provider's own callback) -- callers poll
 * useCheckoutSession/usePaymentIntent afterwards, this mutation doesn't
 * wait for a final outcome itself. */
export function useInitiatePayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { card_number: string }) => {
      const { data, error } = await api.POST("/api/v1/subscriptions/checkout-sessions/current/pay", {
        body: input,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (data) => {
      // The session itself moved to payment_pending server-side.
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      // Real bug found live-testing this phase: without this, the
      // payment-intent query cache still held its PRE-payment result
      // (typically `null`, from the 404 before any intent existed) --
      // usePaymentIntent's `refetchInterval` reads `data?.state` to
      // decide whether to poll, so with stale `null` data it never
      // saw a "pending"/"processing" state to poll FOR, and the
      // checkout page stayed stuck on "Processing…" forever even
      // though the backend had already resolved the payment. Seeding
      // the cache with this response (the intent itself) immediately
      // is what makes polling actually start.
      queryClient.setQueryData(["payment-intent"], data);
    },
  });
}

/** Phase E: the current payment intent -- read once at mount (seeded
 * fresh by useInitiatePayment's own onSuccess right after Pay Now, and
 * invalidated again by the checkout page once useCheckoutSession's own
 * poll sees the session move off payment_pending). No polling on this
 * query itself -- see useCheckoutSession's `pollWhilePaymentPending`
 * for why that single query, not this one, is the actual poll driver.
 * A 404 (no intent yet) is surfaced as `data: null`, matching
 * useCheckoutSession's own 404 handling. */
export function usePaymentIntent() {
  return useQuery({
    queryKey: ["payment-intent"],
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/api/v1/subscriptions/checkout-sessions/current/payment-intent"
      );
      if (response.status === 404) return null;
      if (error) throw error;
      return data;
    },
  });
}

/** Phase F: the step that actually creates the Store. Multipart --
 * `logo` is a real `File`, everything else plain text. `contact_email`
 * is never part of this payload; the backend always uses the
 * authenticated user's own account email. */
export function useSubmitBusinessInfo() {
  return useMutation({
    mutationFn: async (input: {
      store_name: string;
      business_category: string;
      contact_phone: string;
      logo?: File | null;
    }) => {
      const formData = new FormData();
      formData.set("store_name", input.store_name);
      formData.set("business_category", input.business_category);
      formData.set("contact_phone", input.contact_phone);
      if (input.logo) formData.set("logo", input.logo);
      const { data, error } = await api.POST(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        // openapi-fetch types multipart file fields as `string` (no
        // native File-upload typing) -- a real FormData body is the
        // correct wire format regardless; fetch sets the multipart
        // boundary header itself when the body is a FormData instance.
        { body: formData as never }
      );
      if (error) throw error;
      return data;
    },
  });
}
