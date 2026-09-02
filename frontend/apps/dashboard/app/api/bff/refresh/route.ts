import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  accessTokenCookieOptions,
  refreshTokenCookieOptions,
  accessTokenCookieDeleteOptions,
  refreshTokenCookieDeleteOptions,
  refreshWithMutex,
  BackendAuthError,
} from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

/**
 * Called by the `[...path]` proxy on a 401 (or directly by client code
 * that wants to pre-emptively refresh). `refreshWithMutex` collapses
 * concurrent callers in this same process onto one real Django call --
 * see packages/auth/src/refresh-mutex.ts for the documented MVP-vs-Redis
 * tradeoff. A refresh failure (expired/reused/blacklisted token) clears
 * both cookies and returns 401 -- the caller is expected to redirect to
 * /login, never to retry.
 */
export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json({ detail: "No refresh token." }, { status: 401 });
  }

  try {
    const tokens = await refreshWithMutex(refreshToken);
    const response = NextResponse.json({ ok: true });
    response.cookies.set(ACCESS_TOKEN_COOKIE, tokens.access, accessTokenCookieOptions());
    response.cookies.set(REFRESH_TOKEN_COOKIE, tokens.refresh, refreshTokenCookieOptions());
    return response;
  } catch (error) {
    const response = NextResponse.json({ detail: "Session expired." }, { status: 401 });
    // See accessTokenCookieDeleteOptions()'s own docstring -- omitting
    // `secure: true` here made the browser silently keep the stale
    // `__Host-` cookies instead of clearing them on a failed refresh.
    response.cookies.delete({ name: ACCESS_TOKEN_COOKIE, ...accessTokenCookieDeleteOptions() });
    response.cookies.delete({ name: REFRESH_TOKEN_COOKIE, ...refreshTokenCookieDeleteOptions() });
    if (error instanceof BackendAuthError) return response;
    throw error;
  }
}
