"use client";

import { useQuery } from "@tanstack/react-query";

import { clientStorefrontApi } from "@/lib/backend";

export function useAvailability(variantIds: string[]) {
  return useQuery({
    queryKey: ["availability", ...variantIds],
    enabled: variantIds.length > 0,
    queryFn: async () => {
      const { data, error } = await clientStorefrontApi().GET(
        "/api/v1/storefront/inventory/availability",
        { params: { query: { variant: variantIds } } }
      );
      if (error) throw error;
      return data as unknown as Record<string, number>;
    },
  });
}
