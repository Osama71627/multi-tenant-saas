"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { Skeleton } from "@saas/ui/skeleton";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  useCheckoutSession,
  useInitiatePayment,
  usePaymentIntent,
} from "@/lib/hooks/use-checkout-session";
import { usePublicThemePresets } from "@/lib/hooks/use-public-theme-presets";

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    amountMinorUnits / 100
  );
}

// Same imprecision plan-selector.tsx already works around -- Django
// JSONField, no shape drf-spectacular can know.
interface ThemePresetPalette {
  primary_color: string;
}

export function SubscriptionCheckout({
  locale,
  email,
  fullName,
}: {
  locale: string;
  email: string;
  fullName: string;
}) {
  const t = useTranslations("subscriptionCheckout");
  const router = useRouter();
  const queryClient = useQueryClient();
  // Always allow polling -- the query's own refetchInterval callback
  // checks the LATEST cached checkout_status itself (see that hook's
  // comment for the real bug this fixed: coordinating two separate
  // queries, one deciding whether to poll and the other holding the
  // data, left a window where the poll never started at all).
  const { data: session, isLoading: sessionLoading } = useCheckoutSession({
    pollWhilePaymentPending: true,
  });
  const { data: presets } = usePublicThemePresets();
  const initiatePayment = useInitiatePayment();

  const status = session?.checkout_status;
  // The only statuses this page knows how to render -- anything else
  // (draft, no session at all, or already completed into a Store)
  // belongs back on /plans.
  const RENDERABLE = new Set([
    "ready_for_payment",
    "payment_pending",
    "payment_failed",
    "awaiting_business_info",
  ]);
  const renderable = Boolean(status && RENDERABLE.has(status));

  const { data: intent } = usePaymentIntent();

  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");

  useEffect(() => {
    if (!sessionLoading && !renderable) {
      router.replace(`/${locale}/plans`);
    }
  }, [sessionLoading, renderable, router, locale]);

  // The session moving OFF payment_pending (via the poll above) means
  // the webhook-driven backend state has resolved -- refetch the
  // intent too, so the failure screen has a fresh `failure_reason`
  // rather than the mid-flight "pending" one from right after Pay Now.
  useEffect(() => {
    if (status === "payment_failed" || status === "awaiting_business_info") {
      queryClient.invalidateQueries({ queryKey: ["payment-intent"] });
    }
  }, [status, queryClient]);

  const plan = session?.plan_version;
  const preset = presets?.find((p) => p.id === session?.theme_preset_id);
  const palette = preset?.default_settings as ThemePresetPalette | undefined;

  if (sessionLoading || !renderable) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 px-4 py-12">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  // ---- Success: Payment Successful / Ready for Business Information ----
  if (status === "awaiting_business_info") {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
        <CheckCircle2 className="h-12 w-12 text-primary" />
        <h1 className="text-2xl font-semibold">{t("success.title")}</h1>
        <p className="text-muted-foreground">{t("success.body")}</p>
        <Button size="lg" asChild>
          <Link href={`/${locale}/business-info`}>{t("success.cta")}</Link>
        </Button>
      </div>
    );
  }

  // ---- Failure: تعذر إتمام عملية الدفع ----
  if (status === "payment_failed") {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
        <AlertTriangle className="h-12 w-12 text-destructive" />
        <h1 className="text-2xl font-semibold">{t("failure.title")}</h1>
        <p className="text-muted-foreground">
          {intent?.failure_reason ? t(`failure.reason.${intent.failure_reason}`) : t("failure.body")}
        </p>
        <div className="flex gap-3">
          <Button variant="secondary" asChild>
            <Link href={`/${locale}/plans`}>{t("failure.backToPlan")}</Link>
          </Button>
          <Button onClick={() => document.getElementById("retry-anchor")?.scrollIntoView()}>
            {t("failure.retry")}
          </Button>
        </div>
        <div id="retry-anchor" />
        <PaymentForm
          t={t}
          cardNumber={cardNumber}
          setCardNumber={setCardNumber}
          cardExpiry={cardExpiry}
          setCardExpiry={setCardExpiry}
          cardCvc={cardCvc}
          setCardCvc={setCardCvc}
          onSubmit={() => initiatePayment.mutate({ card_number: cardNumber })}
          isPending={initiatePayment.isPending}
          isError={initiatePayment.isError}
        />
      </div>
    );
  }

  // ---- Pending: a demo "webhook" is about to resolve this ----
  if (status === "payment_pending") {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <h1 className="text-xl font-semibold">{t("processing.title")}</h1>
        <p className="text-muted-foreground">{t("processing.body")}</p>
      </div>
    );
  }

  // ---- The real checkout screen: summary + payment method + Pay Now ----
  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-12">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("summary.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <div
              className="h-10 w-10 shrink-0 rounded-lg"
              style={{ background: palette?.primary_color ?? "var(--muted)" }}
            />
            <div>
              <p className="text-sm text-muted-foreground">{t("summary.theme")}</p>
              <p className="font-medium">{preset?.theme_name ?? "—"}</p>
            </div>
          </div>

          <div className="flex items-center justify-between border-t pt-4">
            <div>
              <p className="text-sm text-muted-foreground">{t("summary.plan")}</p>
              <div className="flex items-center gap-2 font-medium">
                {plan?.plan_name} <Badge variant="secondary">{t("summary.monthly")}</Badge>
              </div>
            </div>
            <p className="text-xl font-bold">
              {plan ? formatMoney(plan.price_monthly, plan.currency) : "—"}
            </p>
          </div>

          {plan?.features?.filter((f) => f.enabled).length ? (
            <ul className="space-y-1.5 border-t pt-4 text-sm">
              {plan.features
                .filter((f) => f.enabled)
                .map((f) => (
                  <li key={f.feature_key} className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-primary" />
                    {t(`feature.${f.feature_key}`)}
                  </li>
                ))}
            </ul>
          ) : null}

          <div className="flex items-center justify-between border-t pt-4 font-semibold">
            <span>{t("summary.total")}</span>
            <span>{plan ? formatMoney(plan.price_monthly, plan.currency) : "—"}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("customer.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="checkout-name">{t("customer.name")}</Label>
            <Input id="checkout-name" value={fullName} disabled readOnly />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="checkout-email">{t("customer.email")}</Label>
            <Input id="checkout-email" value={email} disabled readOnly />
          </div>
        </CardContent>
      </Card>

      <PaymentForm
        t={t}
        cardNumber={cardNumber}
        setCardNumber={setCardNumber}
        cardExpiry={cardExpiry}
        setCardExpiry={setCardExpiry}
        cardCvc={cardCvc}
        setCardCvc={setCardCvc}
        onSubmit={() => initiatePayment.mutate({ card_number: cardNumber })}
        isPending={initiatePayment.isPending}
        isError={initiatePayment.isError}
      />
    </div>
  );
}

function PaymentForm({
  t,
  cardNumber,
  setCardNumber,
  cardExpiry,
  setCardExpiry,
  cardCvc,
  setCardCvc,
  onSubmit,
  isPending,
  isError,
}: {
  t: ReturnType<typeof useTranslations>;
  cardNumber: string;
  setCardNumber: (v: string) => void;
  cardExpiry: string;
  setCardExpiry: (v: string) => void;
  cardCvc: string;
  setCardCvc: (v: string) => void;
  onSubmit: () => void;
  isPending: boolean;
  isError: boolean;
}) {
  const canSubmit = cardNumber.trim().length >= 4 && cardExpiry && cardCvc;
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-base">{t("paymentMethod.title")}</CardTitle>
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <ShieldCheck className="h-4 w-4 text-primary" />
          {t("paymentMethod.notice")}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="checkout-card-number">{t("paymentMethod.cardNumber")}</Label>
          <Input
            id="checkout-card-number"
            inputMode="numeric"
            placeholder="4242 4242 4242 4242"
            value={cardNumber}
            onChange={(e) => setCardNumber(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="checkout-card-expiry">{t("paymentMethod.expiry")}</Label>
            <Input
              id="checkout-card-expiry"
              placeholder="MM/YY"
              value={cardExpiry}
              onChange={(e) => setCardExpiry(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="checkout-card-cvc">{t("paymentMethod.cvc")}</Label>
            <Input
              id="checkout-card-cvc"
              inputMode="numeric"
              placeholder="123"
              value={cardCvc}
              onChange={(e) => setCardCvc(e.target.value)}
            />
          </div>
        </div>
        {isError ? <p className="text-sm text-destructive">{t("paymentMethod.error")}</p> : null}
        <Button className="w-full" size="lg" disabled={!canSubmit || isPending} onClick={onSubmit}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : t("paymentMethod.payNow")}
        </Button>
      </CardContent>
    </Card>
  );
}
