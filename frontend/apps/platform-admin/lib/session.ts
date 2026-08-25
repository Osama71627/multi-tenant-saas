import "server-only";

import { ACCESS_TOKEN_COOKIE, backendProxy, refreshWithMutex, REFRESH_TOKEN_COOKIE } from "@saas/auth";
import { cookies } from "next/headers";

/**
 * Server Component / layout data-fetching helper -- same shape as
 * apps/dashboard/lib/session.ts (see that file for the full rationale
 * on the best-effort inline refresh).
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

export interface CurrentPlatformUser {
  id: string;
  email: string;
  full_name: string;
  is_platform_staff: boolean;
}

/**
 * Unlike apps/dashboard's `getCurrentUser` (any authenticated
 * PlatformUser is a valid dashboard user), this ALSO requires
 * `is_platform_staff` -- an ordinary merchant with a perfectly valid
 * session must not be treated as "logged in" for this app. This is a
 * UX convenience only: the real boundary is still every
 * `/api/v1/platform/*` endpoint's `IsPlatformStaff` permission on the
 * Django side (docs/ARCHITECTURE.md's governing principle -- backend
 * stays authoritative).
 */
export async function getCurrentPlatformStaffUser(): Promise<CurrentPlatformUser | null> {
  const response = await serverFetch("api/v1/auth/me");
  if (!response.ok) return null;
  const user: CurrentPlatformUser = await response.json();
  if (!user.is_platform_staff) return null;
  return user;
}

export async function requireAccessTokenCookie(): Promise<boolean> {
  const cookieStore = await cookies();
  return cookieStore.has(ACCESS_TOKEN_COOKIE);
}
