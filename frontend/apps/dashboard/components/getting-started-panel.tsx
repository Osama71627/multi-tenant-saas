"use client";

import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { CreditCard, Eye, Package, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useStore } from "@/lib/hooks/use-store";
import { storefrontUrl } from "@/lib/storefront-url";

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
  const { data: store } = useStore(storeId);

  function dismiss() {
    setDismissed(true);
    router.replace(`/${locale}/stores/${storeId}`);
  }

  if (dismissed) return null;

  // Real gap found live: "Preview store" here always opened the
  // internal fixture-data preview (demo products, not this merchant's
  // real catalog) -- see setup-checklist.tsx's identical fix and its
  // own, more detailed comment. Opens the merchant's real storefront in
  // a new tab now that `store.primary_domain` exists; falls back to the
  // fixture preview only in the genuinely impossible case of a Store
  // with no primary domain row.
  const previewStoreHref = store?.primary_domain
    ? storefrontUrl(store.primary_domain)
    : `/${locale}/stores/${storeId}/preview`;
  const previewStoreIsExternal = Boolean(store?.primary_domain);

  const steps = [
    {
      icon: Package,
      title: t("addProducts.title"),
      body: t("addProducts.body"),
      href: `/${locale}/stores/${storeId}/products`,
      cta: t("addProducts.cta"),
      external: false,
    },
    {
      icon: CreditCard,
      title: t("connectPayments.title"),
      body: t("connectPayments.body"),
      href: `/${locale}/stores/${storeId}/payments`,
      cta: t("connectPayments.cta"),
      external: false,
    },
    {
      icon: Eye,
      title: t("previewStore.title"),
      body: t("previewStore.body"),
      href: previewStoreHref,
      cta: t("previewStore.cta"),
      external: previewStoreIsExternal,
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
              {step.external ? (
                <a href={step.href} target="_blank" rel="noopener noreferrer">
                  {step.cta} →
                </a>
              ) : (
                <Link href={step.href}>{step.cta} →</Link>
              )}
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
