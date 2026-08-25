import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  CSRF_COOKIE,
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
  response.cookies.delete({ name: ACCESS_TOKEN_COOKIE, path: "/" });
  // Must match the exact `path` it was SET with (refreshTokenCookieOptions,
  // "/api/bff/refresh") -- the browser only deletes a cookie whose
  // name+path attribute pair matches; a mismatched path silently no-ops.
  response.cookies.delete({ name: REFRESH_TOKEN_COOKIE, path: "/api/bff/refresh" });
  response.cookies.delete({ name: CSRF_COOKIE, path: "/" });
  return response;
}
