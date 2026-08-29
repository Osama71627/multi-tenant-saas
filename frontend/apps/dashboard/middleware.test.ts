import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import middleware from "./middleware";

const ACCESS_TOKEN_COOKIE = "__Host-at"; // must match @saas/auth/cookies' ACCESS_TOKEN_COOKIE exactly

function requestFor(path: string, cookieValue?: string): NextRequest {
  // Pass the Cookie header directly in the constructor -- NextRequest's
  // `.cookies` is re-derived from the underlying Headers each access, so
  // mutating a post-construction `.cookies.set(...)` call doesn't
  // reliably write back through to it (confirmed live: `.has()` read
  // `false` back after such a `.set()`).
  const headers = cookieValue ? { cookie: `${ACCESS_TOKEN_COOKIE}=${cookieValue}` } : undefined;
  return new NextRequest(new URL(path, "http://localhost:3001"), { headers });
}

describe("middleware -- already-authenticated visitors on /register or /login", () => {
  it("sends an already-logged-in visitor with a ?theme= straight to /plans, never back to the register form", () => {
    const response = middleware(
      requestFor("/en/register?theme=preset-123", "a-valid-looking-token")
    );
    expect(response.status).toBe(307); // NextResponse.redirect default
    expect(response.headers.get("location")).toBe(
      "http://localhost:3001/en/plans?theme=preset-123"
    );
  });

  it("sends an already-logged-in visitor with no theme to /app, not the register form", () => {
    const response = middleware(requestFor("/en/register", "a-valid-looking-token"));
    expect(response.headers.get("location")).toBe("http://localhost:3001/en/app");
  });

  it("sends an already-logged-in visitor away from /login too, honoring ?next= over ?theme=", () => {
    const response = middleware(
      requestFor("/en/login?next=/en/stores/abc&theme=preset-123", "a-valid-looking-token")
    );
    expect(response.headers.get("location")).toBe("http://localhost:3001/en/stores/abc");
  });

  it("leaves a visitor with NO session cookie on the register page -- the real, first-time signup path", () => {
    const response = middleware(requestFor("/en/register?theme=preset-123"));
    // No redirect Location header -- this is next-intl's own pass-through response.
    expect(response.headers.get("location")).toBeNull();
  });
});

describe("middleware -- protected paths still require a session (unchanged behavior)", () => {
  it("still bounces a storeless visitor with no cookie to /login with ?next=", () => {
    const response = middleware(requestFor("/en/stores/abc"));
    expect(response.headers.get("location")).toBe(
      "http://localhost:3001/en/login?next=%2Fen%2Fstores%2Fabc"
    );
  });

  it("lets an authenticated visitor straight through to a protected path", () => {
    const response = middleware(requestFor("/en/stores/abc", "a-valid-looking-token"));
    expect(response.headers.get("location")).toBeNull();
  });
});
