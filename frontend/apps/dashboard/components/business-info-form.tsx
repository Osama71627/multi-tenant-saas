"use client";

import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { Select } from "@saas/ui/select";
import { Skeleton } from "@saas/ui/skeleton";
import { ImagePlus, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useCheckoutSession, useSubmitBusinessInfo } from "@/lib/hooks/use-checkout-session";

const CATEGORY_KEYS = [
  "fashion",
  "electronics",
  "food",
  "beauty",
  "home",
  "services",
  "other",
] as const;

export function BusinessInfoForm({ locale, email }: { locale: string; email: string }) {
  const t = useTranslations("businessInfo");
  const router = useRouter();
  const { data: session, isLoading: sessionLoading } = useCheckoutSession();
  const submitBusinessInfo = useSubmitBusinessInfo();

  const [storeName, setStoreName] = useState("");
  const [category, setCategory] = useState<(typeof CATEGORY_KEYS)[number]>("fashion");
  const [otherCategory, setOtherCategory] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // This page only makes sense right after a successful demo payment --
  // any other session state (nothing yet, still needs a plan, or
  // already completed into a Store) belongs back on /plans.
  useEffect(() => {
    if (!sessionLoading && session?.checkout_status !== "awaiting_business_info") {
      router.replace(`/${locale}/plans`);
    }
  }, [sessionLoading, session?.checkout_status, router, locale]);

  useEffect(() => {
    if (!logoFile) {
      setLogoPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(logoFile);
    setLogoPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [logoFile]);

  if (sessionLoading || session?.checkout_status !== "awaiting_business_info") {
    return (
      <div className="mx-auto max-w-lg space-y-4 px-4 py-16">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const businessCategory = category === "other" ? otherCategory : t(`category.${category}`);
  const canSubmit = storeName.trim() && businessCategory.trim() && contactPhone.trim();

  function handleSubmit() {
    submitBusinessInfo.mutate(
      {
        store_name: storeName.trim(),
        business_category: businessCategory.trim(),
        contact_phone: contactPhone.trim(),
        logo: logoFile,
      },
      {
        onSuccess: (store) => {
          router.push(`/${locale}/stores/${store.id}?welcome=1`);
        },
      }
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 px-4 py-16">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("cardTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <Label>{t("logo")}</Label>
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-dashed bg-muted"
              >
                {logoPreviewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- local object URL preview, next/image optimization doesn't apply
                  <img src={logoPreviewUrl} alt="" className="h-full w-full object-cover" />
                ) : (
                  <ImagePlus className="h-6 w-6 text-muted-foreground" />
                )}
              </button>
              <Button type="button" variant="secondary" onClick={() => fileInputRef.current?.click()}>
                {t("uploadLogo")}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => setLogoFile(e.target.files?.[0] ?? null)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="business-store-name">{t("storeName")}</Label>
            <Input
              id="business-store-name"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="business-category">{t("category.label")}</Label>
            <Select
              id="business-category"
              value={category}
              onChange={(e) => setCategory(e.target.value as (typeof CATEGORY_KEYS)[number])}
            >
              {CATEGORY_KEYS.map((key) => (
                <option key={key} value={key}>
                  {t(`category.${key}`)}
                </option>
              ))}
            </Select>
            {category === "other" ? (
              <Input
                className="mt-2"
                placeholder={t("category.otherPlaceholder")}
                value={otherCategory}
                onChange={(e) => setOtherCategory(e.target.value)}
              />
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="business-phone">{t("contactPhone")}</Label>
            <Input
              id="business-phone"
              type="tel"
              placeholder="+966500000000"
              value={contactPhone}
              onChange={(e) => setContactPhone(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="business-email">{t("contactEmail")}</Label>
            <Input id="business-email" value={email} disabled readOnly />
          </div>

          {submitBusinessInfo.isError ? (
            <p className="text-sm text-destructive">{t("submitError")}</p>
          ) : null}

          <Button className="w-full" disabled={!canSubmit || submitBusinessInfo.isPending} onClick={handleSubmit}>
            {submitBusinessInfo.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              t("submit")
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
