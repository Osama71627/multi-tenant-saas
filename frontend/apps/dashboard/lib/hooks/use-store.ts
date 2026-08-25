"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import type { components } from "@saas/api-client";

export function useStore(storeId: string) {
  return useQuery({
    queryKey: ["store", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/dashboard/stores/{store_id}", {
        params: { path: { store_id: storeId } },
      });
      if (error) throw error;
      return data;
    },
  });
}

export function useUpdateStore(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: components["schemas"]["PatchedUpdateStoreRequest"]) => {
      const { data, error } = await api.PATCH("/api/v1/dashboard/stores/{store_id}", {
        params: { path: { store_id: storeId } },
        body: input,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["store", storeId] });
      queryClient.invalidateQueries({ queryKey: ["stores"] });
    },
  });
}
