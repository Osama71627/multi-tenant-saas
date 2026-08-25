/**
 * Cookie names/options for the BFF token-custody pattern
 * (docs/ARCHITECTURE.md section 6.2). Every cookie is host-only
 * (`__Host-` prefix: forces Secure, Path=/, and forbids a `Domain`
 * attribute at the browser level) -- ARCHITECTURE.md is explicit that
 * using `Domain=.example.com` here would leak a merchant's dashboard
 * session cookie to `store-b.example.com`, which must never happen.
 *
 * `__Host-` requires HTTPS in real browsers; `localhost` is a documented
 * exception every major browser makes (treated as a secure context), so
 * this works unmodified in local dev over plain HTTP on localhost.
 */

export const ACCESS_TOKEN_COOKIE = "__Host-at";
export const REFRESH_TOKEN_COOKIE = "__Host-rt";
export const CSRF_COOKIE = "__Host-csrf";
// Lives here, not in ./csrf, deliberately -- this file has zero Node
// built-in imports, so it's safe for CLIENT components and the Edge
// runtime (middleware.ts) to import; ./csrf pulls in `node:crypto` for
// the actual token generation/comparison, which neither context can load.
export const CSRF_HEADER = "x-csrf-token";

const ACCESS_TOKEN_MAX_AGE_SECONDS = 15 * 60; // mirrors SIMPLE_JWT.ACCESS_TOKEN_LIFETIME
const REFRESH_TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // mirrors SIMPLE_JWT.REFRESH_TOKEN_LIFETIME

export function accessTokenCookieOptions() {
  return {
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: ACCESS_TOKEN_MAX_AGE_SECONDS,
  };
}

export function refreshTokenCookieOptions() {
  return {
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    // Scoped to the refresh endpoint only -- JS/other route handlers
    // never need the refresh token itself, only the BFF's own refresh
    // logic does.
    path: "/api/bff/refresh",
    maxAge: REFRESH_TOKEN_MAX_AGE_SECONDS,
  };
}

export function csrfCookieOptions() {
  return {
    // Deliberately NOT httpOnly -- the double-submit pattern requires
    // client JS to read this value and echo it back in a request header;
    // the cookie alone proves nothing (CSRF-vulnerable requests can't
    // forge a custom header cross-site), it's the pairing that matters.
    httpOnly: false,
    secure: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: ACCESS_TOKEN_MAX_AGE_SECONDS,
  };
}
