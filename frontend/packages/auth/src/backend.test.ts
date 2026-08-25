import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  backendLogin,
  backendMfaEnrollConfirm,
  backendMfaEnrollStart,
  backendMfaVerify,
  BackendAuthError,
} from "./backend";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    })
  );
}

beforeEach(() => {
  process.env.BACKEND_INTERNAL_URL = "http://backend.internal";
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.BACKEND_INTERNAL_URL;
});

describe("backendLogin", () => {
  it("returns a TokenPair for an ordinary account", async () => {
    mockFetchOnce(200, { access: "access-token", refresh: "refresh-token" });
    const result = await backendLogin("merchant@example.com", "correct-h0rse!");
    expect(result).toEqual({ access: "access-token", refresh: "refresh-token" });
  });

  it("returns an MfaChallengeResponse for a platform-staff account", async () => {
    mockFetchOnce(200, { state: "mfa_required", challenge_token: "chal-abc" });
    const result = await backendLogin("staff@example.com", "correct-h0rse!");
    expect(result).toEqual({
      mfaChallenge: true,
      state: "mfa_required",
      challengeToken: "chal-abc",
    });
  });

  it("throws BackendAuthError with the response body on failure", async () => {
    mockFetchOnce(401, { detail: "No active account found with the given credentials" });
    await expect(backendLogin("merchant@example.com", "wrong")).rejects.toMatchObject({
      status: 401,
      body: { detail: "No active account found with the given credentials" },
    });
  });

  it("BackendAuthError is an instance of Error and carries a status", async () => {
    mockFetchOnce(429, { detail: "Try again later." });
    try {
      await backendLogin("merchant@example.com", "wrong");
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(BackendAuthError);
      expect((error as BackendAuthError).status).toBe(429);
    }
  });
});

describe("backendMfaVerify", () => {
  it("returns a TokenPair on success", async () => {
    mockFetchOnce(200, { access: "access-token", refresh: "refresh-token" });
    const result = await backendMfaVerify("chal-abc", "123456");
    expect(result).toEqual({ access: "access-token", refresh: "refresh-token" });
  });

  it("throws on an incorrect code", async () => {
    mockFetchOnce(401, { detail: "Incorrect verification code." });
    await expect(backendMfaVerify("chal-abc", "000000")).rejects.toMatchObject({ status: 401 });
  });
});

describe("backendMfaEnrollStart", () => {
  it("returns the secret and provisioning URI", async () => {
    mockFetchOnce(200, {
      secret: "JBSWY3DPEHPK3PXP",
      provisioning_uri: "otpauth://totp/Platform:staff@example.com",
    });
    const result = await backendMfaEnrollStart("chal-abc");
    expect(result).toEqual({
      secret: "JBSWY3DPEHPK3PXP",
      provisioningUri: "otpauth://totp/Platform:staff@example.com",
    });
  });
});

describe("backendMfaEnrollConfirm", () => {
  it("returns tokens and recovery codes on success", async () => {
    mockFetchOnce(200, {
      access: "access-token",
      refresh: "refresh-token",
      recovery_codes: ["abcde-12345", "fghij-67890"],
    });
    const result = await backendMfaEnrollConfirm("chal-abc", "123456");
    expect(result).toEqual({
      access: "access-token",
      refresh: "refresh-token",
      recoveryCodes: ["abcde-12345", "fghij-67890"],
    });
  });
});
