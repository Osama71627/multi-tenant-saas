import { afterEach, describe, expect, it, vi } from "vitest";

import { randomUUID } from "./uuid";

const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("randomUUID", () => {
  it("uses crypto.randomUUID() when available", () => {
    const spy = vi.spyOn(crypto, "randomUUID");
    const id = randomUUID();
    expect(spy).toHaveBeenCalled();
    expect(id).toMatch(UUID_V4_PATTERN);
  });

  it("falls back to crypto.getRandomValues() when randomUUID is unavailable", () => {
    // Reproduces the real bug this fixes: crypto.randomUUID is undefined
    // on any non-secure-context origin (verified: a plain-HTTP custom
    // local-dev domain like `<store>.lvh.me`, not just some contrived
    // test double) -- checkout silently failed there before this fix.
    vi.stubGlobal("crypto", {
      randomUUID: undefined,
      getRandomValues: crypto.getRandomValues.bind(crypto),
    });
    const id = randomUUID();
    expect(id).toMatch(UUID_V4_PATTERN);
  });

  it("generates unique values across calls", () => {
    const ids = new Set(Array.from({ length: 50 }, () => randomUUID()));
    expect(ids.size).toBe(50);
  });
});
