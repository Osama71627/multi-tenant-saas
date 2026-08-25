import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "./login-form";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  useSearchParams: () => new URLSearchParams(),
}));

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function fillCredentials(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("email"), "staff@example.com");
  await user.type(screen.getByLabelText("password"), "correct-h0rse!");
  await user.click(screen.getByRole("button", { name: "loginButton" }));
}

describe("LoginForm -- ordinary account (no MFA challenge)", () => {
  it("finishes login directly when /api/bff/login returns ok", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
    );
    render(<LoginForm locale="en" />);

    await fillCredentials(user);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/en"));
    expect(refresh).toHaveBeenCalled();
  });

  it("shows a server error and does not navigate on invalid credentials", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(401, { detail: "invalid" }))
    );
    render(<LoginForm locale="en" />);

    await fillCredentials(user);

    expect(await screen.findByText("loginError")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});

describe("LoginForm -- platform-staff account, not yet enrolled", () => {
  it("routes into enrollment and shows the setup secret", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          mfaChallenge: true,
          state: "mfa_setup_required",
          challengeToken: "chal-1",
        })
      )
      .mockResolvedValueOnce(
        jsonResponse(200, { secret: "JBSWY3DPEHPK3PXP", provisioningUri: "otpauth://x" })
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginForm locale="en" />);

    await fillCredentials(user);

    expect(await screen.findByText("mfaSetupTitle")).toBeInTheDocument();
    expect(screen.getByText("JBSWY3DPEHPK3PXP")).toBeInTheDocument();
    // Never issues tokens before a code is confirmed.
    expect(push).not.toHaveBeenCalled();
  });

  it("shows recovery codes after a correct enrollment code, then finishes login", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          mfaChallenge: true,
          state: "mfa_setup_required",
          challengeToken: "chal-1",
        })
      )
      .mockResolvedValueOnce(jsonResponse(200, { secret: "JBSWY3DPEHPK3PXP" }))
      .mockResolvedValueOnce(
        jsonResponse(200, { ok: true, recoveryCodes: ["abcde-12345", "fghij-67890"] })
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginForm locale="en" />);

    await fillCredentials(user);
    await screen.findByText("mfaSetupTitle");

    await user.type(screen.getByLabelText("mfaSetupCodeLabel"), "123456");
    await user.click(screen.getByRole("button", { name: "mfaEnrollButton" }));

    expect(await screen.findByText("mfaRecoveryCodesTitle")).toBeInTheDocument();
    expect(screen.getByText("abcde-12345")).toBeInTheDocument();
    expect(screen.getByText("fghij-67890")).toBeInTheDocument();
    // Tokens were issued by the enroll/confirm call, but navigation only
    // happens once the user acknowledges the recovery codes.
    expect(push).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "mfaContinueButton" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/en"));
  });
});

describe("LoginForm -- platform-staff account, already enrolled", () => {
  it("prompts for a TOTP code and finishes login on success", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, { mfaChallenge: true, state: "mfa_required", challengeToken: "chal-2" })
      )
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginForm locale="en" />);

    await fillCredentials(user);

    expect(await screen.findByText("mfaVerifyTitle")).toBeInTheDocument();
    await user.type(screen.getByLabelText("mfaCodeLabel"), "654321");
    await user.click(screen.getByRole("button", { name: "mfaVerifyButton" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/en"));
  });

  it("shows the server's error message and stays on the verify step for a wrong code", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, { mfaChallenge: true, state: "mfa_required", challengeToken: "chal-2" })
      )
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Incorrect verification code." }));
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginForm locale="en" />);

    await fillCredentials(user);
    await screen.findByText("mfaVerifyTitle");

    await user.type(screen.getByLabelText("mfaCodeLabel"), "000000");
    await user.click(screen.getByRole("button", { name: "mfaVerifyButton" }));

    expect(await screen.findByText("Incorrect verification code.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
    // Still on the verify step, not bounced back to credentials.
    expect(screen.getByText("mfaVerifyTitle")).toBeInTheDocument();
  });
});
