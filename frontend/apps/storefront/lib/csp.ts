/**
 * Phase 17 -- Content-Security-Policy for this app's middleware. Zero
 * imports on purpose: `crypto.randomUUID()`/`btoa()` are runtime globals
 * (Edge runtime + browser). See apps/dashboard/lib/csp.ts's docstring for
 * why this is duplicated per-app rather than shared via a `@saas/*`
 * package (a real `EvalError` under `next start`'s sandboxed Edge
 * simulation, only found by testing a production build).
 *
 * Deny-by-default, nonce + `strict-dynamic` for scripts (the officially
 * documented Next.js pattern). `style-src-attr: 'unsafe-inline'` is the
 * one deliberate exception -- the theme system (`@saas/theme-aurora`,
 * approved Phase 13) injects a merchant's theme colors as CSS custom
 * properties via React's inline `style={{...}}` prop, and CSP
 * nonces/hashes apply only to `<style>` ELEMENTS, never to a `style=""`
 * ATTRIBUTE (a spec limitation, not a Next.js one).
 *
 * `backendOrigin` is a parameter here, unlike dashboard/platform-admin's
 * fixed `'self'`: this app's browser client calls Django directly
 * (`lib/backend.ts`'s `browserBackendOrigin()`), a genuinely different
 * origin in dev (`:8000` vs this app's own port) -- see middleware.ts.
 * The SAME origin is also allowed in `img-src` for the identical
 * reason: a store's uploaded logo (Store.logo, Phase F) is served by
 * Django directly, not proxied through this app -- real bug found
 * live, `img-src`'s original `'self' data:'` (Phase 17, before any
 * theme rendered a real image at all) silently blocked every logo
 * `<img>` in every theme's header/footer, discovered only by reading
 * the browser's own console (an `<img>` failing CSP fails silent-ish:
 * no network request, no visible error in the element itself, just a
 * broken image -- `naturalWidth: 0` alone doesn't distinguish this
 * from a genuine 404).
 *
 * `style-src-elem`'s hash allowlist has one entry: `react-remove-scroll`
 * (a transitive dependency of `@radix-ui/react-select`, used by
 * `@saas/ui/select` -- checkout's shipping/payment method pickers use
 * it) injects a fixed, static `<style>` element to lock body scroll
 * while a popover is open. Its content never varies by page/props, so
 * its SHA-256 hash is a stable, exact, real fix -- found via an actual
 * checkout run (`frontend/e2e`) that failed with the browser's own CSP
 * violation report giving this exact hash, not guessed. Never widen this
 * to `'unsafe-inline'`; add a new hash only if a real violation names one.
 */

export function generateNonce(): string {
  return btoa(crypto.randomUUID());
}

const REACT_REMOVE_SCROLL_STYLE_HASH = "'sha256-nzTgYzXYDNe6BAHiiI7NNlfK8n/auuOAhh2t92YvuXo='";

export function buildCsp(nonce: string, backendOrigin: string): string {
  return [
    "default-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src-elem 'self' ${REACT_REMOVE_SCROLL_STYLE_HASH}`,
    "style-src-attr 'unsafe-inline'",
    `img-src 'self' data: ${backendOrigin}`,
    "font-src 'self'",
    `connect-src 'self' ${backendOrigin}`,
  ].join("; ");
}
