import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  CSRF_COOKIE,
  accessTokenCookieOptions,
  refreshTokenCookieOptions,
  csrfCookieOptions,
  generateCsrfToken,
  backendMfaEnrollConfirm,
  BackendAuthError,
} from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

/**
 * Second step of enrollment: {challengeToken, code} -> confirms the
 * device, sets the same auth cookies /api/bff/login would, and returns
 * the one-time recovery codes RAW so the client can display them exactly
 * once -- they are never retrievable again after this response.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.challengeToken || !body?.code) {
    return NextResponse.json({ detail: "challengeToken and code are required." }, { status: 400 });
  }

  try {
    const { access, refresh, recoveryCodes } = await backendMfaEnrollConfirm(
      body.challengeToken,
      body.code
    );
    const response = NextResponse.json({ ok: true, recoveryCodes });
    response.cookies.set(ACCESS_TOKEN_COOKIE, access, accessTokenCookieOptions());
    response.cookies.set(REFRESH_TOKEN_COOKIE, refresh, refreshTokenCookieOptions());
    response.cookies.set(CSRF_COOKIE, generateCsrfToken(), csrfCookieOptions());
    return response;
  } catch (error) {
    if (error instanceof BackendAuthError) {
      return NextResponse.json(error.body, { status: error.status });
    }
    throw error;
  }
}
