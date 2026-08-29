import { describe, expect, it } from "vitest";

import { buildCsp, generateNonce } from "./csp";

describe("generateNonce", () => {
  it("returns a non-empty string, different each call", () => {
    const a = generateNonce();
    const b = generateNonce();
    expect(a).toBeTruthy();
    expect(a).not.toBe(b);
  });
});

describe("buildCsp", () => {
  const nonce = "test-nonce-value";
  const backendOrigin = "http://storefront.lvh.me:8000";
  const csp = buildCsp(nonce, backendOrigin);

  it("is deny-by-default", () => {
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("frame-ancestors 'none'");
  });

  it("uses nonce + strict-dynamic for scripts, never unsafe-inline or unsafe-eval", () => {
    expect(csp).toContain(`script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`);
    expect(csp).not.toContain("unsafe-eval");
    const scriptSrcDirective = csp.split(";").find((d) => d.trim().startsWith("script-src"));
    expect(scriptSrcDirective).not.toContain("unsafe-inline");
  });

  it("allows only the given backend origin in connect-src, not a wildcard", () => {
    const connectSrcDirective = csp.split(";").find((d) => d.trim().startsWith("connect-src"));
    expect(connectSrcDirective).toContain(backendOrigin);
    expect(connectSrcDirective).toContain("'self'");
    expect(connectSrcDirective).not.toContain("*");
  });

  it("allows the same backend origin in img-src, not a wildcard -- real bug found live: a store's uploaded logo is served by Django directly, silently blocked otherwise", () => {
    const imgSrcDirective = csp.split(";").find((d) => d.trim().startsWith("img-src"));
    expect(imgSrcDirective).toContain(backendOrigin);
    expect(imgSrcDirective).toContain("'self'");
    expect(imgSrcDirective).toContain("data:");
    expect(imgSrcDirective).not.toContain("*");
  });

  it("relaxes style-src-attr, and style-src-elem only by the one known react-remove-scroll hash", () => {
    expect(csp).toContain("style-src-attr 'unsafe-inline'");
    const styleElemDirective = csp.split(";").find((d) => d.trim().startsWith("style-src-elem"));
    expect(styleElemDirective).not.toContain("unsafe-inline");
    expect(styleElemDirective).toContain(
      "'sha256-nzTgYzXYDNe6BAHiiI7NNlfK8n/auuOAhh2t92YvuXo='"
    );
  });
});
