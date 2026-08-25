"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@saas/ui/button";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const credentialsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
type CredentialsValues = z.infer<typeof credentialsSchema>;

type Step =
  | { name: "credentials" }
  | { name: "mfaVerify"; challengeToken: string }
  | { name: "mfaEnroll"; challengeToken: string; secret: string }
  | { name: "mfaRecoveryCodes"; codes: string[] };

interface BffLoginResponse {
  ok?: boolean;
  detail?: string;
  mfaChallenge?: boolean;
  state?: "mfa_required" | "mfa_setup_required";
  challengeToken?: string;
  secret?: string;
  recoveryCodes?: string[];
}

async function postJson(
  url: string,
  body: unknown
): Promise<{ ok: boolean; data: BffLoginResponse }> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json().catch(() => ({}))) as BffLoginResponse;
  return { ok: response.ok, data };
}

/**
 * Phase 17 -- platform-staff accounts (the only accounts that ever log
 * into this app, per docs/ARCHITECTURE.md section 7.4) always go through
 * MFA: /api/bff/login returns a challenge instead of a session whenever
 * `is_platform_staff=True`. This form is a small state machine over that
 * two-step flow (mfaVerify for an already-enrolled device, mfaEnroll +
 * mfaRecoveryCodes for a first-time setup) rather than four separate
 * pages, since every step needs the same `challengeToken` in scope and
 * none of it is bookmarkable/shareable state.
 */
export function LoginForm({ locale }: { locale: string }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>({ name: "credentials" });
  const [serverError, setServerError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [pending, setPending] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CredentialsValues>({ resolver: zodResolver(credentialsSchema) });

  function finishLogin() {
    const next = searchParams.get("next") ?? `/${locale}`;
    router.push(next);
    router.refresh();
  }

  async function onSubmitCredentials(values: CredentialsValues) {
    setServerError(null);
    const { ok, data } = await postJson("/api/bff/login", values);
    if (!ok) {
      setServerError(t("loginError"));
      return;
    }
    if (data.mfaChallenge && data.challengeToken) {
      const challengeToken = data.challengeToken;
      if (data.state === "mfa_setup_required") {
        setPending(true);
        const start = await postJson("/api/bff/mfa/enroll/start", { challengeToken });
        setPending(false);
        if (!start.ok || !start.data.secret) {
          setServerError(t("loginError"));
          return;
        }
        setStep({ name: "mfaEnroll", challengeToken, secret: start.data.secret });
      } else {
        setStep({ name: "mfaVerify", challengeToken });
      }
      return;
    }
    finishLogin();
  }

  async function onSubmitMfaVerify(challengeToken: string) {
    setServerError(null);
    setPending(true);
    const { ok, data } = await postJson("/api/bff/mfa/verify", { challengeToken, code });
    setPending(false);
    if (!ok) {
      setServerError(data.detail ?? t("mfaInvalidCode"));
      return;
    }
    finishLogin();
  }

  async function onSubmitMfaEnrollConfirm(challengeToken: string) {
    setServerError(null);
    setPending(true);
    const { ok, data } = await postJson("/api/bff/mfa/enroll/confirm", { challengeToken, code });
    setPending(false);
    if (!ok) {
      setServerError(data.detail ?? t("mfaInvalidCode"));
      return;
    }
    setStep({ name: "mfaRecoveryCodes", codes: data.recoveryCodes ?? [] });
  }

  if (step.name === "mfaVerify") {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">{t("mfaVerifyTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("mfaVerifySubtitle")}</p>
        <div className="space-y-1.5">
          <Label htmlFor="mfa-code">{t("mfaCodeLabel")}</Label>
          <Input
            id="mfa-code"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        {serverError ? <p className="text-sm text-destructive">{serverError}</p> : null}
        <Button
          type="button"
          className="w-full"
          disabled={pending || !code}
          onClick={() => onSubmitMfaVerify(step.challengeToken)}
        >
          {t("mfaVerifyButton")}
        </Button>
      </div>
    );
  }

  if (step.name === "mfaEnroll") {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">{t("mfaSetupTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("mfaSetupSubtitle")}</p>
        <p className="text-sm text-muted-foreground">{t("mfaSetupInstructions")}</p>
        <div className="space-y-1.5">
          <Label>{t("mfaSecretLabel")}</Label>
          <code className="block rounded border bg-muted px-3 py-2 text-sm tracking-widest">
            {step.secret}
          </code>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="mfa-setup-code">{t("mfaSetupCodeLabel")}</Label>
          <Input
            id="mfa-setup-code"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        {serverError ? <p className="text-sm text-destructive">{serverError}</p> : null}
        <Button
          type="button"
          className="w-full"
          disabled={pending || !code}
          onClick={() => onSubmitMfaEnrollConfirm(step.challengeToken)}
        >
          {t("mfaEnrollButton")}
        </Button>
      </div>
    );
  }

  if (step.name === "mfaRecoveryCodes") {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">{t("mfaRecoveryCodesTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("mfaRecoveryCodesSubtitle")}</p>
        <ul className="grid grid-cols-2 gap-2 rounded border bg-muted p-3 font-mono text-sm">
          {step.codes.map((recoveryCode) => (
            <li key={recoveryCode}>{recoveryCode}</li>
          ))}
        </ul>
        <Button type="button" className="w-full" onClick={finishLogin}>
          {t("mfaContinueButton")}
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmitCredentials)} className="space-y-4">
      <h1 className="text-xl font-semibold">{t("loginTitle")}</h1>

      <div className="space-y-1.5">
        <Label htmlFor="email">{t("email")}</Label>
        <Input id="email" type="email" autoComplete="email" {...register("email")} />
        {errors.email ? <p className="text-xs text-destructive">{errors.email.message}</p> : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="password">{t("password")}</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          {...register("password")}
        />
        {errors.password ? (
          <p className="text-xs text-destructive">{errors.password.message}</p>
        ) : null}
      </div>

      {serverError ? <p className="text-sm text-destructive">{serverError}</p> : null}

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {t("loginButton")}
      </Button>
    </form>
  );
}
