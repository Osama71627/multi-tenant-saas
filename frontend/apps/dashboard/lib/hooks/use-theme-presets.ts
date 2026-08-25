"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useThemePresets() {
  return useQuery({
    queryKey: ["theme-presets"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/dashboard/theme-presets");
      if (error) throw error;
      return data;
    },
  });
}
