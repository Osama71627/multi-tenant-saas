"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useStores() {
  return useQuery({
    queryKey: ["stores"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/dashboard/stores");
      if (error) throw error;
      return data;
    },
  });
}
