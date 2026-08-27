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

const schema = z.object({
  full_name: z.string().min(1),
  email: z.string().email(),
  password: z.string().min(8),
});
type FormValues = z.infer<typeof schema>;

export function RegisterForm({ locale }: { locale: string }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const searchParams = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setServerError(null);
    const registerResponse = await fetch("/api/bff/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!registerResponse.ok) {
      const data = await registerResponse.json().catch(() => null);
      setServerError(data?.detail ?? data?.email?.[0] ?? "Registration failed.");
      return;
    }

    const loginResponse = await fetch("/api/bff/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: values.email, password: values.password }),
    });
    if (!loginResponse.ok) {
      router.push(`/${locale}/login`);
      return;
    }
    // A theme selected on the public marketplace before registering
    // (Phase B) survives the auth transition via this plain, non-
    // sensitive query param -- the plan-selection page (Phase D)
    // attaches it to the new user's checkout session server-side.
    const themePresetId = searchParams.get("theme");
    router.push(themePresetId ? `/${locale}/plans?theme=${themePresetId}` : `/${locale}/app`);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <h1 className="text-xl font-semibold">{t("registerTitle")}</h1>

      <div className="space-y-1.5">
        <Label htmlFor="full_name">Full name</Label>
        <Input id="full_name" autoComplete="name" {...register("full_name")} />
        {errors.full_name ? (
          <p className="text-xs text-destructive">{errors.full_name.message}</p>
        ) : null}
      </div>

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
          autoComplete="new-password"
          {...register("password")}
        />
        {errors.password ? (
          <p className="text-xs text-destructive">{errors.password.message}</p>
        ) : null}
      </div>

      {serverError ? <p className="text-sm text-destructive">{serverError}</p> : null}

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {t("registerButton")}
      </Button>
    </form>
  );
}
