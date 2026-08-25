"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import type { components } from "@saas/api-client";

export function useStockBalances(storeId: string) {
  return useQuery({
    queryKey: ["inventory-balances", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/inventory/balances",
        { params: { path: { store_id: storeId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useStockLocations(storeId: string) {
  return useQuery({
    queryKey: ["inventory-locations", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/inventory/locations",
        { params: { path: { store_id: storeId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useCreateStockLocation(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: components["schemas"]["StockLocationRequest"]) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/inventory/locations",
        { params: { path: { store_id: storeId } }, body: input }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-locations", storeId] });
    },
  });
}

export function useAdjustStock(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: components["schemas"]["AdjustStockRequest"]) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/inventory/adjust",
        { params: { path: { store_id: storeId } }, body: input }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-balances", storeId] });
    },
  });
}
