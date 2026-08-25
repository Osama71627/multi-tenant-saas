import { randomBytes, timingSafeEqual } from "node:crypto";

/**
 * Double-submit CSRF token (docs/ARCHITECTURE.md section 6.2: "CSRF:
 * double-submit token لكل طلب mutating عبر الـ BFF"). The token itself
 * carries no secret meaning -- what proves the request is same-origin is
 * that the value in the `X-CSRF-Token` header matches the value in the
 * (non-httpOnly) cookie, which only same-origin JS can read.
 *
 * `CSRF_HEADER`/`CSRF_COOKIE` themselves live in `./cookies` (re-exported
 * below for backward-compatible imports from the `@saas/auth` barrel),
 * NOT here -- this module pulls in `node:crypto`, which breaks any
 * CLIENT component that imports it (confirmed while building this:
 * `lib/api-client.ts` needed just the header/cookie NAME constants, but
 * importing them from the barrel dragged `node:crypto` into the browser
 * bundle). Client code must import the constants from `@saas/auth/cookies`
 * specifically, never the barrel.
 */
export { CSRF_HEADER } from "./cookies";

export function generateCsrfToken(): string {
  return randomBytes(32).toString("base64url");
}

export function csrfTokensMatch(cookieValue: string | undefined, headerValue: string | null): boolean {
  if (!cookieValue || !headerValue) return false;
  const a = Buffer.from(cookieValue);
  const b = Buffer.from(headerValue);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}
