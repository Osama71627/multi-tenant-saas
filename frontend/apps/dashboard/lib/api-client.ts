"use client";

// `@saas/auth/cookies`, NOT the barrel -- this is a CLIENT component
// (browser bundle), and the barrel transitively pulls in `node:crypto`
// via `@saas/auth/src/csrf.ts`'s token-generation functions, which no
// browser bundle can resolve (confirmed while building this).
import { CSRF_COOKIE, CSRF_HEADER } from "@saas/auth/cookies";
import { createApiClient } from "@saas/api-client";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  const value = match?.[1];
  return value ? decodeURIComponent(value) : null;
}

/**
 * The client component-facing API client -- attaches the double-submit
 * CSRF header (docs/ARCHITECTURE.md section 6.2) to every mutating
 * request. The token itself is read from the (deliberately non-httpOnly)
 * CSRF cookie set at login -- see packages/auth/src/cookies.ts's
 * `csrfCookieOptions` docstring for why that one specific cookie is
 * readable by JS while the actual session tokens never are.
 */
export const api = createApiClient();

api.use({
  onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) {
      const token = readCookie(CSRF_COOKIE);
      if (token) request.headers.set(CSRF_HEADER, token);
    }
    return request;
  },
});
