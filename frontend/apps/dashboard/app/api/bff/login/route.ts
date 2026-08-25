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
 * docs/ARCHITECTURE.md section 6.2's BFF sequence diagram, step 1-2:
 * browser posts credentials here (no CSRF check on THIS request --
 * there's no session yet to forge), the BFF calls Django directly, and
 * on success sets the httpOnly token cookies + a fresh CSRF cookie.
 * The access/refresh tokens themselves are NEVER sent back in the JSON
 * body -- only httpOnly cookies carry them, so client JS can't read them
 * even by accident (the whole point of the BFF pattern).
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ detail: "email and password are required." }, { status: 400 });
  }

  try {
    const result = await backendLogin(body.email, body.password);
    // Phase 17: only platform-staff accounts ever get a challenge instead
    // of tokens (apps.accounts.mfa_services) -- staff are meant to use
    // apps/platform-admin, not this app (docs/ARCHITECTURE.md section
    // 7.4), so this is an unsupported-account error here, not a flow to
    // build a second MFA UI for.
    if ("mfaChallenge" in result) {
      return NextResponse.json(
        { detail: "This account must sign in through the Platform Admin app." },
        { status: 400 }
      );
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
