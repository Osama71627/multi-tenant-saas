"use client";

import { Button } from "@saas/ui/button";
import { CheckCircle2 } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";

import { formatMoney } from "@/lib/format-money";

export default function ConfirmationPage() {
  const { locale } = useParams<{ locale: string }>();
  const searchParams = useSearchParams();
  const t = useTranslations("storefront.confirmation");

  const number = searchParams.get("number");
  const total = searchParams.get("total");
  const currency = searchParams.get("currency");

  return (
    <div className="mx-auto max-w-md px-4 py-20 text-center">
      <CheckCircle2 className="mx-auto h-12 w-12" style={{ color: "var(--sf-primary)" }} />
      <h1 className="mt-4 text-xl font-semibold">{t("title")}</h1>
      {number ? (
        <p className="mt-2 text-sm text-gray-600">
          {t("orderNumber")}: <span className="font-medium">{number}</span>
        </p>
      ) : null}
      {total && currency ? (
        <p className="mt-1 text-sm text-gray-600">{formatMoney(Number(total), currency)}</p>
      ) : null}
      <p className="mt-4 text-xs text-gray-400">{t("emailNotice")}</p>
      <Button asChild className="mt-8" style={{ backgroundColor: "var(--sf-primary)" }}>
        <Link href={`/${locale}`}>{t("backToShop")}</Link>
      </Button>
    </div>
  );
}
