import type { AuroraSettings } from "@saas/theme-aurora";
import { headers } from "next/headers";

import { serverStorefrontApi } from "@/lib/backend";

export interface StorefrontContext {
  store: { id: string; name: string; default_currency: string };
  theme: {
    theme_code: string;
    theme_version_number: number;
    settings: AuroraSettings;
  };
}

/** The current request's real hostname (the shopper's, not Next's own
 * server address) -- captured once here so every server-side caller
 * derives it the same way. */
export async function currentHostname(): Promise<string> {
  const h = await headers();
  return (h.get("host") ?? "").split(":")[0] ?? "";
}

export async function getStorefrontContext(): Promise<StorefrontContext | null> {
  const hostname = await currentHostname();
  if (!hostname) return null;

  const api = serverStorefrontApi(hostname);
  const { data, error } = await api.GET("/api/v1/storefront/context");
  if (error || !data) return null;

  return data as unknown as StorefrontContext;
}
