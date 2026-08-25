"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import type { components } from "@saas/api-client";

export function usePaymentProviders(storeId: string) {
  return useQuery({
    queryKey: ["payment-providers", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/payments/providers",
        { params: { path: { store_id: storeId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useConnectPaymentProvider(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: components["schemas"]["StoreProviderConfigRequest"]) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/payments/providers",
        { params: { path: { store_id: storeId } }, body: input }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["payment-providers", storeId] });
    },
  });
}
