import createClient from "openapi-fetch";
import type { paths } from "@saas/api-client";

/**
 * Unlike the dashboard, the storefront has no JWT/cookie-security reason
 * for a BFF proxy -- there's no signed-in user, only a guest cart cookie
 * that Django sets directly (httponly, host-scoped to whichever hostname
 * issued it). So the browser talks to Django directly; CORS already
 * allows any `*.lvh.me` origin with credentials (config/settings/local.py).
 *
 * Tenant resolution is Host-header-based on the Django side
 * (apps/stores/middleware.py) -- for a genuine browser request, the
 * browser's own Host IS the tenant hostname, so nothing extra is needed
 * here. The only place that needs help is server-side rendering (Next's
 * RSC), where "the request" is Next's OWN server calling Django, not the
 * shopper's browser -- see `serverStorefrontApi` below.
 */
const BACKEND_PORT = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8000";

function browserBackendOrigin(): string {
  if (typeof window === "undefined") {
    throw new Error("browserBackendOrigin() called outside the browser");
  }
  return `${window.location.protocol}//${window.location.hostname}:${BACKEND_PORT}`;
}

/**
 * The server-side equivalent of `browserBackendOrigin()` -- same
 * "tenant hostname + Django's real port" construction, for code that
 * runs before the browser ever sees the page (e.g. turning the
 * storefront context's relative `store.logo` path into a real `<img
 * src>` the shopper's OWN eventual page load can reach -- see
 * apps.themes.serializers.StorefrontStoreSerializer.get_logo's own
 * docstring for why that field is relative in the first place).
 * `hostname` must already be bare (no port) -- pass the same value
 * `currentHostname()`'s caller would strip for tenant lookup, not its
 * raw forwarded value. Hardcodes `http:` -- this whole project is
 * local-dev/staging only so far (no TLS termination for `*.lvh.me`
 * exists anywhere yet); a real production origin scheme is a separate,
 * not-yet-designed concern, same as production media storage itself
 * (config/urls.py's own dev-only media-serving comment).
 */
export function serverBackendOrigin(hostname: string): string {
  return `http://${hostname}:${BACKEND_PORT}`;
}

/** Client-component API client -- call from `"use client"` code only. */
export function clientStorefrontApi() {
  return createClient<paths>({ baseUrl: browserBackendOrigin(), credentials: "include" });
}

/**
 * Server-component/route-handler API client. Forwards the INCOMING
 * request's real hostname (captured by the caller via `next/headers`,
 * since that API is only callable from a server context) as
 * `X-Forwarded-Host` -- Django's `USE_X_FORWARDED_HOST=True`
 * (config/settings/base.py) reads that in place of its own `Host`
 * header for exactly this hop. Never guesses/derives the hostname any
 * other way.
 */
export function serverStorefrontApi(hostname: string) {
  const base = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
  const client = createClient<paths>({ baseUrl: base, cache: "no-store" });
  client.use({
    onRequest({ request }) {
      request.headers.set("X-Forwarded-Host", hostname);
      return request;
    },
  });
  return client;
}
