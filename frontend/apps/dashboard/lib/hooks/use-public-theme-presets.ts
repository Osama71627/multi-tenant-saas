"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

/** Phase B's public theme marketplace data source, reused here (Phase
 * D) to resolve a `theme_preset_id` stored on a checkout session back
 * to a real name/category/preview -- `apps.subscriptions` cannot do
 * this resolution itself (see SubscriptionCheckoutSession's docstring
 * on the import-linter layering that prevents it), so the frontend,
 * which already has this full list from the marketplace, matches it
 * locally instead. */
export function usePublicThemePresets() {
  return useQuery({
    queryKey: ["public-theme-presets"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/themes/public/presets");
      if (error) throw error;
      return data;
    },
  });
}
