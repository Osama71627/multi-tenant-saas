/**
 * Phase 17 -- Content-Security-Policy for this app's middleware. Zero
 * imports on purpose: `crypto.randomUUID()`/`btoa()` are runtime globals
 * (Edge runtime + browser), and this file must stay in THIS app, not a
 * shared `@saas/*` package -- importing this logic from a workspace
 * package alongside `@saas/auth/cookies` in the same middleware.ts
 * bundled a Node `crypto` polyfill into the Edge middleware chunk that
 * throws `EvalError: Code generation from strings disallowed` at runtime
 * under `next start`'s sandboxed Edge simulation (never surfaced in `next
 * dev`, which doesn't sandbox as strictly -- only found by testing a real
 * production build, exactly the check Phase 17 requires). Duplicated
 * verbatim across apps/{dashboard,platform-admin,storefront}/lib/csp.ts
 * rather than shared, to guarantee no cross-package bundling risk.
 *
 * Deny-by-default, nonce + `strict-dynamic` for scripts (the officially
 * documented Next.js pattern: a nonce'd script may load further scripts
 * Next itself injects for chunk-loading/hydration, without listing every
 * chunk URL or falling back to `unsafe-inline`).
 *
 * `style-src-attr: 'unsafe-inline'` is one deliberate, unavoidable
 * exception: this app's own components can still set inline `style={{}}`
 * (e.g. chart colors). CSP nonces/hashes apply only to `<style>`
 * ELEMENTS, never to a `style=""` ATTRIBUTE -- a CSP spec limitation, not
 * a Next.js one, so there is no nonce/hash alternative here.
 *
 * `style-src-elem`'s hash allowlist has one entry: `react-remove-scroll`
 * (a transitive dependency of `@radix-ui/react-select`/`-dialog`, used
 * throughout `@saas/ui`) injects a fixed, static `<style>` element to
 * lock body scroll while a popover/dialog is open. Its content never
 * varies by page/props, so its SHA-256 hash is a stable, exact, real
 * fix -- found via an actual checkout run (`frontend/e2e`) that failed
 * with the browser's own CSP violation report giving this exact hash,
 * not guessed (this app shares the same `@saas/ui` components, so the
 * same fix applies here even though the violation was first reproduced
 * on the storefront). Never widen either exception to a blanket
 * `'unsafe-inline'` on the element form; add a new hash only if a real
 * violation names one.
 */

export function generateNonce(): string {
  return btoa(crypto.randomUUID());
}

const REACT_REMOVE_SCROLL_STYLE_HASH = "'sha256-nzTgYzXYDNe6BAHiiI7NNlfK8n/auuOAhh2t92YvuXo='";

export function buildCsp(nonce: string): string {
  return [
    "default-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src-elem 'self' ${REACT_REMOVE_SCROLL_STYLE_HASH}`,
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
  ].join("; ");
}
