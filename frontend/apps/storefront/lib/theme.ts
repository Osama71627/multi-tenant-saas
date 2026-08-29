import type { AuroraSettings } from "@saas/theme-aurora";
import { headers } from "next/headers";

import { serverBackendOrigin, serverStorefrontApi } from "@/lib/backend";

export interface StorefrontContext {
  store: { id: string; name: string; default_currency: string; logo: string | null };
  theme: {
    theme_code: string;
    theme_version_number: number;
    settings: AuroraSettings;
  };
}

/** The current request's real host (the shopper's, not Next's own
 * server address) -- captured once here so every server-side caller
 * derives it the same way. Kept WITH its port (if any) -- Django's own
 * tenant resolution (`apps.stores.middleware._resolve_by_host`) strips
 * the port itself before looking up the tenant, so forwarding it
 * unmodified via `X-Forwarded-Host` changes nothing there and is
 * simply the more faithful thing to forward. */
export async function currentHostname(): Promise<string> {
  const h = await headers();
  return h.get("host") ?? "";
}

export async function getStorefrontContext(): Promise<StorefrontContext | null> {
  const hostname = await currentHostname();
  if (!hostname) return null;

  const api = serverStorefrontApi(hostname);
  const { data, error } = await api.GET("/api/v1/storefront/context");
  if (error || !data) return null;

  const context = data as unknown as StorefrontContext;
  return {
    ...context,
    store: { ...context.store, logo: absoluteLogoUrl(context.store.logo, hostname) },
  };
}

/**
 * `apps.themes.serializers.StorefrontStoreSerializer.get_logo` returns
 * a relative path (`/media/...`), deliberately -- see that method's own
 * docstring for why it can't safely build the full URL itself (the
 * storefront's Next server and Django genuinely sit on different ports
 * in local dev, both reachable through the SAME tenant hostname, so
 * Django has no way to know which port the shopper's own browser
 * should ultimately load the image from). This is the other half of
 * that fix: apply the exact same "tenant hostname + Django's real
 * port" construction `lib/backend.ts`'s `browserBackendOrigin()`
 * already uses for every other storefront API call, just server-side
 * (before the page ever reaches the browser) instead of client-side.
 */
function absoluteLogoUrl(relativeLogoPath: string | null, hostname: string): string | null {
  if (!relativeLogoPath) return null;
  const bareHostname = hostname.split(":")[0] ?? hostname;
  return `${serverBackendOrigin(bareHostname)}${relativeLogoPath}`;
}
