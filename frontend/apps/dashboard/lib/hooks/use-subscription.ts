"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useSubscription(storeId: string) {
  return useQuery({
    queryKey: ["subscription", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/subscription",
        { params: { path: { store_id: storeId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}
