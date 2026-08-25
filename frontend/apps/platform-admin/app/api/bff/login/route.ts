import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  CSRF_COOKIE,
  accessTokenCookieOptions,
  refreshTokenCookieOptions,
  csrfCookieOptions,
  generateCsrfToken,
  backendLogin,
  BackendAuthError,
} from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

/**
 * Same JWT `platform` realm as apps/dashboard -- platform staff log in
 * through the exact same /api/v1/auth/login endpoint as merchants;
 * `is_platform_staff` (not a separate realm) is what distinguishes them,
 * checked server-side by (app)/layout.tsx after login, and ultimately by
 * every /api/v1/platform/* endpoint's IsPlatformStaff permission.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ detail: "email and password are required." }, { status: 400 });
  }

  try {
    const result = await backendLogin(body.email, body.password);
    // Phase 17: a platform-staff account never gets a JWT here -- only an
    // opaque challenge token. No cookies are set until MfaVerify/
    // MfaEnrollConfirm below succeeds; the client branches on `state`.
    if ("mfaChallenge" in result) {
      return NextResponse.json({
        mfaChallenge: true,
        state: result.state,
        challengeToken: result.challengeToken,
      });
    }
    const response = NextResponse.json({ ok: true });
    response.cookies.set(ACCESS_TOKEN_COOKIE, result.access, accessTokenCookieOptions());
    response.cookies.set(REFRESH_TOKEN_COOKIE, result.refresh, refreshTokenCookieOptions());
    response.cookies.set(CSRF_COOKIE, generateCsrfToken(), csrfCookieOptions());
    return response;
  } catch (error) {
    if (error instanceof BackendAuthError) {
      return NextResponse.json(error.body, { status: error.status });
    }
    throw error;
  }
}
