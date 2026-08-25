"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useOrders(storeId: string) {
  return useQuery({
    queryKey: ["orders", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/dashboard/stores/{store_id}/orders", {
        params: { path: { store_id: storeId } },
      });
      if (error) throw error;
      return data;
    },
  });
}

export function useOrder(storeId: string, orderId: string) {
  return useQuery({
    queryKey: ["order", storeId, orderId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/orders/{order_id}",
        { params: { path: { store_id: storeId, order_id: orderId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}
