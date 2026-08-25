/**
 * `crypto.randomUUID()` requires a secure context (HTTPS, or the literal
 * hostname `localhost`/`127.0.0.1`) -- it is `undefined` on any other
 * plain-HTTP origin, including a real custom local-dev domain like
 * `<store>.lvh.me` (verified: `window.isSecureContext` is `false` and
 * `crypto.randomUUID` is `undefined` there). Checkout's idempotency keys
 * used it directly, so placing an order silently failed (an uncaught
 * `TypeError` swallowed by the page's own try/catch, no console output,
 * no network call ever made) on any such origin -- caught only by
 * actually running the E2E purchase flow (`frontend/e2e`), not by
 * `next dev`/`next build` or any unit test. `crypto.getRandomValues()`
 * has no such restriction, so it's the fallback here rather than a
 * third-party UUID package -- one extra RFC 4122 v4 formatting step is
 * enough.
 */
export function randomUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40; // version 4
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80; // variant 10
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}
