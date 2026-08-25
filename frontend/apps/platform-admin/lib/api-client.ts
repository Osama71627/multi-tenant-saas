"use client";

// `@saas/auth/cookies`, NOT the barrel -- this is a CLIENT component
// (browser bundle), and the barrel transitively pulls in `node:crypto`
// via `@saas/auth/src/csrf.ts`'s token-generation functions, which no
// browser bundle can resolve.
import { CSRF_COOKIE, CSRF_HEADER } from "@saas/auth/cookies";
import { createApiClient } from "@saas/api-client";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  const value = match?.[1];
  return value ? decodeURIComponent(value) : null;
}

/**
 * Same pattern as apps/dashboard/lib/api-client.ts -- attaches the
 * double-submit CSRF header to every mutating request.
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
