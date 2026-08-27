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
export function useCheckoutSession() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/subscriptions/checkout-sessions/current");
      if (response.status === 404) return null;
      if (error) throw error;
      return data;
    },
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
