"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { clientStorefrontApi } from "@/lib/backend";

const CART_KEY = ["cart"];

export function useCart() {
  return useQuery({
    queryKey: CART_KEY,
    queryFn: async () => {
      const { data, error } = await clientStorefrontApi().GET("/api/v1/storefront/cart");
      if (error) throw error;
      return data;
    },
  });
}

export function useAddToCart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { variant: string; quantity: number }) => {
      const { data, error } = await clientStorefrontApi().POST("/api/v1/storefront/cart/items", {
        body: input,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(CART_KEY, data);
    },
  });
}

export function useUpdateCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ itemId, quantity }: { itemId: string; quantity: number }) => {
      const { data, error } = await clientStorefrontApi().PATCH(
        "/api/v1/storefront/cart/items/{item_id}",
        { params: { path: { item_id: itemId } }, body: { quantity } }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(CART_KEY, data);
    },
  });
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (itemId: string) => {
      const { error } = await clientStorefrontApi().DELETE(
        "/api/v1/storefront/cart/items/{item_id}",
        { params: { path: { item_id: itemId } } }
      );
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CART_KEY });
    },
  });
}
