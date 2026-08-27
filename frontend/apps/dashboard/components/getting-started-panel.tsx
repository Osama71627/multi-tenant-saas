"use client";

import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { CreditCard, Eye, Package, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * The one-time "how do I use this thing" screen the user asked for
 * right after Phase F's business-info step, before landing on the real
 * (otherwise identical) store dashboard. Driven purely by the `?welcome=1`
 * query param business-info-form.tsx's redirect appends -- no DB flag,
 * no "has this merchant seen onboarding" column. Dismissing strips the
 * param via a client-side replace, so a refresh (or any later visit
 * without that exact param) never shows it again -- genuinely one-time,
 * without inventing persistent state for something this disposable.
 */
export function GettingStartedPanel({ locale, storeId }: { locale: string; storeId: string }) {
  const t = useTranslations("gettingStarted");
  const router = useRouter();
  const [dismissed, setDismissed] = useState(false);

  function dismiss() {
    setDismissed(true);
    router.replace(`/${locale}/stores/${storeId}`);
  }

  if (dismissed) return null;

  const steps = [
    {
      icon: Package,
      title: t("addProducts.title"),
      body: t("addProducts.body"),
      href: `/${locale}/stores/${storeId}/products`,
      cta: t("addProducts.cta"),
    },
    {
      icon: CreditCard,
      title: t("connectPayments.title"),
      body: t("connectPayments.body"),
      href: `/${locale}/stores/${storeId}/payments`,
      cta: t("connectPayments.cta"),
    },
    {
      icon: Eye,
      title: t("previewStore.title"),
      body: t("previewStore.body"),
      href: `/${locale}/stores/${storeId}/preview`,
      cta: t("previewStore.cta"),
    },
  ];

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>{t("title")}</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button variant="secondary" size="icon" onClick={dismiss} aria-label={t("dismiss")}>
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {steps.map((step) => (
          <div key={step.title} className="space-y-2 rounded-lg border bg-background p-4">
            <step.icon className="h-5 w-5 text-primary" />
            <p className="font-medium">{step.title}</p>
            <p className="text-sm text-muted-foreground">{step.body}</p>
            <Button asChild variant="link" className="h-auto p-0">
              <Link href={step.href}>{step.cta} →</Link>
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
