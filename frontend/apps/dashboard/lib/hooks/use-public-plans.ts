"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

/** Phase D: the plan-selection screen's data source -- real, dynamic
 * PlanVersion rows (price/features/quotas), never hardcoded in the
 * component. Genuinely public (no auth token required by the
 * endpoint), but this hook is only ever mounted on the authenticated
 * plan-selection page in this phase. */
export function usePublicPlans() {
  return useQuery({
    queryKey: ["public-plans"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/subscriptions/plans/public");
      if (error) throw error;
      return data;
    },
  });
}
