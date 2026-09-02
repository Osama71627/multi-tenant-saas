import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  CSRF_COOKIE,
  accessTokenCookieDeleteOptions,
  refreshTokenCookieDeleteOptions,
  csrfCookieDeleteOptions,
  backendLogout,
} from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
  if (refreshToken) {
    // Best-effort: even if Django's blacklist call fails, the cookies
    // still get cleared below -- the browser session ends either way.
    await backendLogout(refreshToken).catch(() => undefined);
  }

  const response = NextResponse.json({ ok: true });
  // Must match the exact `path` (and, for the `__Host-` prefixed names,
  // `secure: true`) each cookie was SET with -- see
  // accessTokenCookieDeleteOptions()'s own docstring for the real bug
  // this once caused: omitting `secure` here made the browser silently
  // reject the whole deletion, so "Log out" appeared to do nothing.
  response.cookies.delete({ name: ACCESS_TOKEN_COOKIE, ...accessTokenCookieDeleteOptions() });
  response.cookies.delete({ name: REFRESH_TOKEN_COOKIE, ...refreshTokenCookieDeleteOptions() });
  response.cookies.delete({ name: CSRF_COOKIE, ...csrfCookieDeleteOptions() });
  return response;
}
