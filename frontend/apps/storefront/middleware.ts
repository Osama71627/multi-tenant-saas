import { defaultLocale, locales } from "@saas/i18n";
import createMiddleware from "next-intl/middleware";
import { NextRequest } from "next/server";

import { buildCsp, generateNonce } from "./lib/csp";

// No auth gate here (unlike apps/dashboard/middleware.ts) -- the
// storefront has no signed-in user, just locale routing. Tenant
// resolution happens entirely on the Django side, from the real Host
// header (apps/stores/middleware.py) -- this middleware never touches
// tenant state.
const intlMiddleware = createMiddleware({
  locales,
  defaultLocale,
  localePrefix: "always",
});

// Mirrors lib/backend.ts's `browserBackendOrigin()` exactly: the
// storefront's client components call Django directly (no BFF, no
// signed-in session to protect -- see that file's docstring), on the
// SAME hostname but a different port. `connect-src` has to name that
// exact origin, computed the same way, or every product/cart/checkout
// fetch from the browser would violate CSP.
const BACKEND_PORT = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8000";

export default function middleware(request: NextRequest) {
  const nonce = generateNonce();
  // Deliberately `request.headers.get("host")`, NOT `request.nextUrl.
  // hostname` -- the latter does not reliably reflect the real incoming
  // Host header (verified: it silently fell back to "localhost" for a
  // request that genuinely arrived on `<store-slug>.lvh.me`, which built
  // a `connect-src` the browser's own same-host fetch never matched --
  // every cart/checkout call was CSP-blocked, only found via a real E2E
  // run since `next dev` doesn't reproduce it). `request.headers.get
  // ("host")` is the same raw value Django's own Host-header tenant
  // resolution uses (apps/stores/middleware.py) -- one source of truth.
  const host = request.headers.get("host") ?? request.nextUrl.host;
  const hostname = host.split(":")[0];
  const backendOrigin = `${request.nextUrl.protocol}//${hostname}:${BACKEND_PORT}`;
  const csp = buildCsp(nonce, backendOrigin);

  const response = intlMiddleware(request);
  // See apps/dashboard/middleware.ts's comment -- Next.js self-applies
  // this nonce to its own injected inline scripts from this header.
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
