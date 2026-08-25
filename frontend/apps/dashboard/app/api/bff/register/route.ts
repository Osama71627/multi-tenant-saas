import { backendRegister, BackendAuthError } from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

/**
 * Registration doesn't establish a session by itself (Django's
 * RegisterView returns the created user, not tokens -- see
 * apps/accounts/views.py:RegisterView) -- the client follows up with a
 * normal /api/bff/login call afterward using the same credentials.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ detail: "email and password are required." }, { status: 400 });
  }

  try {
    const user = await backendRegister(body);
    return NextResponse.json(user, { status: 201 });
  } catch (error) {
    if (error instanceof BackendAuthError) {
      return NextResponse.json(error.body, { status: error.status });
    }
    throw error;
  }
}
