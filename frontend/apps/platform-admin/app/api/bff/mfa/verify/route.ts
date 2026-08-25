import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  CSRF_COOKIE,
  accessTokenCookieOptions,
  refreshTokenCookieOptions,
  csrfCookieOptions,
  generateCsrfToken,
  backendMfaVerify,
  BackendAuthError,
} from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

/**
 * Second step of platform-staff login (already-enrolled device):
 * {challengeToken, code} -> real JWT cookies, same shape as /api/bff/
 * login's success path. No auth cookie exists yet at this point, so
 * (like /api/bff/login) this needs no CSRF check.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.challengeToken || !body?.code) {
    return NextResponse.json({ detail: "challengeToken and code are required." }, { status: 400 });
  }

  try {
    const tokens = await backendMfaVerify(body.challengeToken, body.code);
    const response = NextResponse.json({ ok: true });
    response.cookies.set(ACCESS_TOKEN_COOKIE, tokens.access, accessTokenCookieOptions());
    response.cookies.set(REFRESH_TOKEN_COOKIE, tokens.refresh, refreshTokenCookieOptions());
    response.cookies.set(CSRF_COOKIE, generateCsrfToken(), csrfCookieOptions());
    return response;
  } catch (error) {
    if (error instanceof BackendAuthError) {
      return NextResponse.json(error.body, { status: error.status });
    }
    throw error;
  }
}
