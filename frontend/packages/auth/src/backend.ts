/**
 * Server-only fetch helpers that call Django directly -- never used from
 * client components (this whole package is imported only by Route
 * Handlers, which run on the Node server). `BACKEND_INTERNAL_URL` is a
 * plain env var, not exposed to the browser (no `NEXT_PUBLIC_` prefix):
 * the browser only ever talks to `/api/bff/*` on the SAME origin as the
 * Next.js app, matching the BFF diagram exactly (B->>N, never B->>D).
 */

function backendBaseUrl(): string {
  const url = process.env.BACKEND_INTERNAL_URL;
  if (!url) {
    throw new Error(
      "BACKEND_INTERNAL_URL is not set -- the BFF has no Django backend to talk to."
    );
  }
  return url.replace(/\/$/, "");
}

export interface TokenPair {
  access: string;
  refresh: string;
}

/**
 * Phase 17 -- returned by /auth/login INSTEAD of a TokenPair when the
 * account is platform staff (`is_platform_staff=True`). No JWT exists
 * yet at this point; `challengeToken` is a short-lived, single-use
 * opaque credential that only the mfa/verify or mfa/enroll/* endpoints
 * below can redeem -- see apps.accounts.mfa_services on the backend.
 */
export interface MfaChallengeResponse {
  mfaChallenge: true;
  state: "mfa_required" | "mfa_setup_required";
  challengeToken: string;
}

export class BackendAuthError extends Error {
  constructor(
    public status: number,
    public body: unknown
  ) {
    super(`Backend auth call failed with status ${status}`);
  }
}

async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(`${backendBaseUrl()}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
}

export async function backendLogin(
  email: string,
  password: string
): Promise<TokenPair | MfaChallengeResponse> {
  const response = await postJson("/api/v1/auth/login", { email, password });
  const data = await response.json();
  if (!response.ok) throw new BackendAuthError(response.status, data);
  if ("state" in data && "challenge_token" in data) {
    return { mfaChallenge: true, state: data.state, challengeToken: data.challenge_token };
  }
  return { access: data.access, refresh: data.refresh };
}

export async function backendMfaVerify(challengeToken: string, code: string): Promise<TokenPair> {
  const response = await postJson("/api/v1/auth/mfa/verify", {
    challenge_token: challengeToken,
    code,
  });
  const data = (await response.json()) as TokenPair;
  if (!response.ok) throw new BackendAuthError(response.status, data);
  return { access: data.access, refresh: data.refresh };
}

export async function backendMfaEnrollStart(
  challengeToken: string
): Promise<{ secret: string; provisioningUri: string }> {
  const response = await postJson("/api/v1/auth/mfa/enroll/start", {
    challenge_token: challengeToken,
  });
  const data = await response.json();
  if (!response.ok) throw new BackendAuthError(response.status, data);
  return { secret: data.secret, provisioningUri: data.provisioning_uri };
}

export async function backendMfaEnrollConfirm(
  challengeToken: string,
  code: string
): Promise<TokenPair & { recoveryCodes: string[] }> {
  const response = await postJson("/api/v1/auth/mfa/enroll/confirm", {
    challenge_token: challengeToken,
    code,
  });
  const data = await response.json();
  if (!response.ok) throw new BackendAuthError(response.status, data);
  return { access: data.access, refresh: data.refresh, recoveryCodes: data.recovery_codes };
}

export async function backendRegister(input: {
  email: string;
  password: string;
  name?: string;
}): Promise<unknown> {
  const response = await postJson("/api/v1/auth/register", input);
  const data: unknown = await response.json();
  if (!response.ok) throw new BackendAuthError(response.status, data);
  return data;
}

export async function backendRefresh(refreshToken: string): Promise<TokenPair> {
  const response = await postJson("/api/v1/auth/refresh", { refresh: refreshToken });
  const data = (await response.json()) as TokenPair;
  if (!response.ok) throw new BackendAuthError(response.status, data);
  // ROTATE_REFRESH_TOKENS is on (config/settings/base.py) -- the backend
  // always returns a new refresh token alongside the new access token,
  // never just the access token alone.
  return { access: data.access, refresh: data.refresh };
}

export async function backendLogout(refreshToken: string): Promise<void> {
  await fetch(`${backendBaseUrl()}/api/v1/auth/logout`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${refreshToken}`,
    },
    body: JSON.stringify({ refresh: refreshToken }),
    cache: "no-store",
  });
}

/**
 * Generic authenticated proxy call -- the BFF's `/api/bff/[...path]`
 * catch-all forwards here with whatever access token it currently has,
 * as does `apps/dashboard/lib/session.ts`'s Server Component fetch
 * helper. `path` is the FULL backend path including the "api/v1/"
 * prefix (e.g. "api/v1/dashboard/stores") -- deliberately not added
 * here, so callers that already have the real path (the catch-all route
 * captures "/api/bff/api/v1/..." 1:1, per packages/api-client's
 * `baseUrl: "/api/bff"`) don't end up with it doubled.
 *
 * Never retries internally: 401 handling/refresh is the CALLER's job
 * (apps/dashboard/app/api/bff/[...path]/route.ts, lib/session.ts),
 * because only the caller has the httpOnly refresh-token cookie needed
 * to get a new one.
 */
export async function backendProxy(
  path: string,
  init: {
    method: string;
    accessToken: string | null;
    body?: BodyInit | null;
    contentType?: string | null;
  }
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (init.accessToken) headers.authorization = `Bearer ${init.accessToken}`;
  if (init.contentType) headers["content-type"] = init.contentType;

  const normalizedPath = path.replace(/^\/+/, "");
  return fetch(`${backendBaseUrl()}/${normalizedPath}`, {
    method: init.method,
    headers,
    body: init.body ?? undefined,
    cache: "no-store",
  });
}
