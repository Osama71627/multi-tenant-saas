// Deliberately `@saas/auth/cookies`, NOT the `@saas/auth` barrel --
// middleware runs in the Edge runtime by default, which doesn't support
// `node:crypto` (used by `@saas/auth/src/csrf.ts`, also re-exported from
// the barrel). `cookies.ts` itself has zero Node-built-in imports, so
// this subpath is genuinely Edge-safe; importing the barrel here broke
// the build with an unresolvable `node:crypto` webpack error (verified
// while building this).
import { ACCESS_TOKEN_COOKIE } from "@saas/auth/cookies";
import { defaultLocale, locales } from "@saas/i18n";
import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";

import { buildCsp, generateNonce } from "./lib/csp";

const intlMiddleware = createMiddleware({
  locales,
  defaultLocale,
  localePrefix: "always",
});

const PUBLIC_PATH_SEGMENTS = new Set(["login", "register", "themes"]);

/**
 * Two jobs: (1) next-intl's own locale-prefix routing/negotiation, (2) a
 * fast, UX-only redirect to /login when there's no access-token cookie
 * at all. This is NOT the real authorization boundary -- Django remains
 * authoritative (docs/ARCHITECTURE.md's governing principle) and every
 * BFF route/page re-checks properly; a merchant with an expired-but-
 * present cookie still reaches the real page and gets refreshed or
 * bounced there, not here. This only saves a wasted round trip for the
 * common "never logged in" case.
 */
export default function middleware(request: NextRequest) {
  const nonce = generateNonce();
  const csp = buildCsp(nonce);

  const segments = request.nextUrl.pathname.split("/").filter(Boolean);
  const pathAfterLocale = segments[1]; // segments[0] is the locale
  // The bare locale root (no further segment, e.g. "/en") is the public
  // landing page (app/[locale]/(public)/page.tsx) -- Phase A's "product
  // vision reset" moved the authenticated dashboard entry point to
  // "/[locale]/app" specifically so the root could become public.
  const isPublicPath = !pathAfterLocale || PUBLIC_PATH_SEGMENTS.has(pathAfterLocale);
  const hasAccessTokenCookie = request.cookies.has(ACCESS_TOKEN_COOKIE);

  if (!isPublicPath && !hasAccessTokenCookie) {
    const locale = segments[0] && locales.includes(segments[0] as never) ? segments[0] : defaultLocale;
    const loginUrl = new URL(`/${locale}/login`, request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    const redirectResponse = NextResponse.redirect(loginUrl);
    redirectResponse.headers.set("Content-Security-Policy", csp);
    return redirectResponse;
  }

  const response = intlMiddleware(request);
  // Next.js applies this same nonce to its OWN internally-injected inline
  // scripts by reading it back out of this exact response header -- no
  // extra request-header plumbing needed unless a future page adds a
  // manual inline <script>, which would then need an explicit `nonce`
  // prop threaded via `headers()` (see ./lib/csp.ts's docstring).
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
