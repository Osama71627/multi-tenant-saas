"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import type { components } from "@saas/api-client";

export function useProducts(storeId: string) {
  return useQuery({
    queryKey: ["products", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/products",
        { params: { path: { store_id: storeId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useCreateProduct(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: components["schemas"]["CreateProductRequest"]) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/products",
        { params: { path: { store_id: storeId } }, body: input }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products", storeId] });
    },
  });
}

export function useUpdateProductStatus(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      productId,
      status,
    }: {
      productId: string;
      status: components["schemas"]["PatchedUpdateProductRequest"]["status"];
    }) => {
      const { data, error } = await api.PATCH(
        "/api/v1/dashboard/stores/{store_id}/products/{product_id}",
        { params: { path: { store_id: storeId, product_id: productId } }, body: { status } }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products", storeId] });
    },
  });
}
