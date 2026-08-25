import { describe, expect, it } from "vitest";

import { buildCsp, generateNonce } from "./csp";

describe("generateNonce", () => {
  it("returns a non-empty string, different each call", () => {
    const a = generateNonce();
    const b = generateNonce();
    expect(a).toBeTruthy();
    expect(b).toBeTruthy();
    expect(a).not.toBe(b);
  });
});

describe("buildCsp", () => {
  const nonce = "test-nonce-value";
  const csp = buildCsp(nonce);

  it("is deny-by-default", () => {
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("base-uri 'self'");
  });

  it("uses nonce + strict-dynamic for scripts, never unsafe-inline or unsafe-eval", () => {
    expect(csp).toContain(`script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`);
    expect(csp).not.toContain("unsafe-eval");
    const scriptSrcDirective = csp.split(";").find((d) => d.trim().startsWith("script-src"));
    expect(scriptSrcDirective).not.toContain("unsafe-inline");
  });

  it("relaxes style-src-attr, and style-src-elem only by the one known react-remove-scroll hash", () => {
    expect(csp).toContain("style-src-attr 'unsafe-inline'");
    expect(csp).toContain("style-src-elem 'self'");
    const styleElemDirective = csp.split(";").find((d) => d.trim().startsWith("style-src-elem"));
    expect(styleElemDirective).not.toContain("unsafe-inline");
    expect(styleElemDirective).toContain(
      "'sha256-nzTgYzXYDNe6BAHiiI7NNlfK8n/auuOAhh2t92YvuXo='"
    );
  });

  it("embeds a fresh nonce every call", () => {
    const other = buildCsp(generateNonce());
    expect(other).not.toBe(csp);
  });
});
