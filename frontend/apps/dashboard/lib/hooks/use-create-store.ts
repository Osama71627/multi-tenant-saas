"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useCreateStore() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string; slug: string; theme_preset_id?: string }) => {
      const { data, error } = await api.POST("/api/v1/dashboard/stores", { body: input });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stores"] });
    },
  });
}
