// Deliberately `@saas/auth/cookies`, NOT the `@saas/auth` barrel --
// middleware runs in the Edge runtime by default, which doesn't support
// `node:crypto` (used by `@saas/auth/src/csrf.ts`, also re-exported from
// the barrel). `cookies.ts` itself has zero Node-built-in imports, so
// this subpath is genuinely Edge-safe.
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

// No "register" here on purpose -- platform staff accounts are
// provisioned directly (Django admin / a migration/fixture), never
// self-registered through this app. See docs/ARCHITECTURE.md section
// 7.4: platform-admin is a separate, staff-only surface.
const PUBLIC_PATH_SEGMENTS = new Set(["login"]);

/**
 * Two jobs, same shape as apps/dashboard/middleware.ts: (1) next-intl's
 * locale-prefix routing, (2) a fast, UX-only redirect to /login when
 * there's no access-token cookie at all. NOT the real authorization
 * boundary -- `is_platform_staff` is enforced server-side by
 * `(app)/layout.tsx` (calls /auth/me) and, ultimately, by every
 * `/api/v1/platform/*` endpoint's `IsPlatformStaff` permission on the
 * Django side. A merchant with a valid-but-non-staff session cookie
 * passes this check and only gets bounced once the real check runs.
 */
export default function middleware(request: NextRequest) {
  const nonce = generateNonce();
  const csp = buildCsp(nonce);

  const segments = request.nextUrl.pathname.split("/").filter(Boolean);
  const pathAfterLocale = segments[1]; // segments[0] is the locale
  const isPublicPath = pathAfterLocale ? PUBLIC_PATH_SEGMENTS.has(pathAfterLocale) : false;
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
  // See apps/dashboard/middleware.ts's comment -- Next.js self-applies
  // this nonce to its own injected inline scripts from this header.
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
