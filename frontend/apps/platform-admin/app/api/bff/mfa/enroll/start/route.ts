import { backendMfaEnrollStart, BackendAuthError } from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

/**
 * First step of enrollment (state: mfa_setup_required from /api/bff/
 * login): generates a pending TOTP secret. No cookies are involved --
 * the challenge token alone proves the caller just supplied the correct
 * password.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.challengeToken) {
    return NextResponse.json({ detail: "challengeToken is required." }, { status: 400 });
  }

  try {
    const { secret, provisioningUri } = await backendMfaEnrollStart(body.challengeToken);
    return NextResponse.json({ secret, provisioningUri });
  } catch (error) {
    if (error instanceof BackendAuthError) {
      return NextResponse.json(error.body, { status: error.status });
    }
    throw error;
  }
}
