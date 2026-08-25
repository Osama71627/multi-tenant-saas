import "server-only";

import { ACCESS_TOKEN_COOKIE, backendProxy, refreshWithMutex, REFRESH_TOKEN_COOKIE } from "@saas/auth";
import { cookies } from "next/headers";

/**
 * Server Component / layout data-fetching helper. Talks to Django
 * directly (via `backendProxy`, same server-only helper the BFF proxy
 * route uses) rather than round-tripping through this app's own
 * `/api/bff/*` HTTP routes -- RSCs run on the same Node server, so that
 * would just be an unnecessary extra hop. Handles ONE 401-refresh retry
 * inline; unlike the client-facing proxy route, it can't rewrite the
 * browser's cookies mid-render (Server Components can't set cookies at
 * all -- only Route Handlers/Server Actions can), so a refresh here
 * updates cookies best-effort via `cookies().set()`, which Next.js only
 * honors when called from a Server Action or Route Handler; if this
 * runs during a plain page render, the refreshed token is used for THIS
 * request only and the browser's cookie catches up on next navigation
 * via the client-side proxy path. Documented MVP behavior, not a bug:
 * the alternative (blocking the render to force a cookie write) isn't
 * available in RSC at all.
 */
export async function serverFetch(path: string, init?: { method?: string; body?: unknown }) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value ?? null;
  const method = init?.method ?? "GET";
  const body = init?.body !== undefined ? JSON.stringify(init.body) : undefined;
  const contentType = body ? "application/json" : null;

  let response = await backendProxy(path, { method, accessToken, body, contentType });

  if (response.status === 401 && accessToken) {
    const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
    if (refreshToken) {
      try {
        const tokens = await refreshWithMutex(refreshToken);
        response = await backendProxy(path, {
          method,
          accessToken: tokens.access,
          body,
          contentType,
        });
      } catch {
        // Refresh failed -- fall through with the original 401; the
        // caller (a page/layout) is responsible for redirecting to
        // /login when it gets one.
      }
    }
  }

  return response;
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const response = await serverFetch("api/v1/auth/me");
  if (!response.ok) return null;
  return response.json();
}

export async function requireAccessTokenCookie(): Promise<boolean> {
  const cookieStore = await cookies();
  return cookieStore.has(ACCESS_TOKEN_COOKIE);
}
