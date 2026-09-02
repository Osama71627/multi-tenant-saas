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

/**
 * Real bug found live: "Log out" silently did nothing (session survived
 * a hard reload) because every `response.cookies.delete({ name, path })`
 * call site across the three BFF routes that clear these cookies passed
 * only `{ name, path }` -- omitting `secure: true`. The `__Host-` prefix
 * (see this file's own module docstring) requires EVERY Set-Cookie for
 * that name, deletions included, to carry `Secure` or the browser drops
 * the header entirely and silently keeps the original cookie. Verified
 * live via a raw `curl -D -` against /api/bff/logout: the response's own
 * `set-cookie: __Host-at=; Path=/; Expires=...` line was missing
 * `Secure`, which Chrome/Edge/Firefox all require present-or-reject for
 * a `__Host-`-prefixed name -- confirmed by the subsequent authenticated
 * proxy call still succeeding after "logout".
 *
 * These three helpers exist so every deletion call site spreads the
 * exact same `{ path, secure: true }` pair the matching `*CookieOptions()`
 * above used to SET it, instead of re-typing (and potentially
 * re-omitting) it inline at each of the three route files that clear
 * these cookies (logout, the generic proxy's definitive-401 fallback,
 * refresh's own failure path).
 */
export function accessTokenCookieDeleteOptions() {
  return { path: "/", secure: true };
}

export function refreshTokenCookieDeleteOptions() {
  return { path: "/api/bff/refresh", secure: true };
}

export function csrfCookieDeleteOptions() {
  return { path: "/", secure: true };
}
