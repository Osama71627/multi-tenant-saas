import { describe, expect, it } from "vitest";

import {
  accessTokenCookieDeleteOptions,
  accessTokenCookieOptions,
  csrfCookieDeleteOptions,
  csrfCookieOptions,
  refreshTokenCookieDeleteOptions,
  refreshTokenCookieOptions,
} from "./cookies";

/**
 * Real bug this guards against: "Log out" appeared to do nothing --
 * the session survived a hard reload -- because every cookie-deletion
 * call site passed `{ name, path }` only, omitting `secure: true`. A
 * `__Host-`-prefixed cookie (see cookies.ts's own module docstring)
 * requires EVERY Set-Cookie for that name, deletions included, to carry
 * `Secure`, or the browser silently drops the header and keeps the
 * original cookie. Confirmed live via `curl -D -` against
 * /api/bff/logout before the fix: the response's own
 * `set-cookie: __Host-at=; Path=/; Expires=...` line had no `Secure`.
 *
 * These tests assert each delete-options helper carries `secure: true`
 * and the exact same `path` its matching set-options helper used --
 * a mismatched path is the OTHER way a browser silently no-ops a
 * cookie deletion.
 */
describe("cookie delete options match their set options (path) and are __Host--safe (secure)", () => {
  it("access token", () => {
    expect(accessTokenCookieDeleteOptions()).toEqual({ path: "/", secure: true });
    expect(accessTokenCookieDeleteOptions().path).toBe(accessTokenCookieOptions().path);
  });

  it("refresh token", () => {
    expect(refreshTokenCookieDeleteOptions()).toEqual({
      path: "/api/bff/refresh",
      secure: true,
    });
    expect(refreshTokenCookieDeleteOptions().path).toBe(refreshTokenCookieOptions().path);
  });

  it("csrf", () => {
    expect(csrfCookieDeleteOptions()).toEqual({ path: "/", secure: true });
    expect(csrfCookieDeleteOptions().path).toBe(csrfCookieOptions().path);
  });
});
