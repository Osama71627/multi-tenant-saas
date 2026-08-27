import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@saas/ui/card";
import { CreditCard, Globe, Package, ShieldCheck, Store } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

const FEATURES = [
  { key: "security", icon: ShieldCheck },
  { key: "commerce", icon: Package },
  { key: "payments", icon: CreditCard },
  { key: "bilingual", icon: Globe },
] as const;
const STEP_KEYS = ["step1", "step2", "step3", "step4"] as const;

/**
 * Public landing page -- the new root of the dashboard app as of Phase
 * A's "product vision reset". Replaces the old authenticated-only root
 * (moved to (app)/app/page.tsx); an anonymous visitor now sees this
 * instead of an immediate redirect to /login. No auth, no store
 * context, no client interactivity required -- a plain server
 * component, matching the low-risk scope of this phase (Blueprint's
 * Phase A: landing page only, marketplace/preview come in Phase B/C).
 */
export default async function LandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("landing");
  const year = new Date().getFullYear();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-2 font-semibold">
            <Store className="h-5 w-5" />
            {t("brand")}
          </div>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <a href="#features" className="hover:text-foreground">
              {t("features.title")}
            </a>
            <a href="#how-it-works" className="hover:text-foreground">
              {t("howItWorks.title")}
            </a>
            <a href="#pricing" className="hover:text-foreground">
              {t("pricing.title")}
            </a>
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href={`/${locale}/login`}
              className="text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              {t("logIn")}
            </Link>
            <Button asChild size="sm">
              <Link href={`/${locale}/register`}>{t("hero.primaryCta")}</Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-4xl px-4 py-24 text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{t("hero.headline")}</h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            {t("hero.subheadline")}
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg">
              <Link href={`/${locale}/register`}>{t("hero.primaryCta")}</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href={`/${locale}/themes`}>{t("hero.secondaryCta")}</Link>
            </Button>
          </div>
        </section>

        <section id="features" className="border-t bg-muted/20 py-20">
          <div className="mx-auto max-w-6xl px-4">
            <h2 className="text-center text-2xl font-semibold tracking-tight">
              {t("features.title")}
            </h2>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {FEATURES.map(({ key, icon: Icon }) => (
                <Card key={key}>
                  <CardHeader>
                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <CardTitle className="text-base">{t(`features.${key}.title`)}</CardTitle>
                    <CardDescription>{t(`features.${key}.description`)}</CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section id="how-it-works" className="py-20">
          <div className="mx-auto max-w-6xl px-4">
            <h2 className="text-center text-2xl font-semibold tracking-tight">
              {t("howItWorks.title")}
            </h2>
            <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {STEP_KEYS.map((key, index) => (
                <div key={key} className="text-center">
                  <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {index + 1}
                  </div>
                  <h3 className="text-sm font-semibold">{t(`howItWorks.${key}.title`)}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {t(`howItWorks.${key}.description`)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="border-t bg-muted/20 py-20">
          <div className="mx-auto max-w-2xl px-4 text-center">
            <Card>
              <CardHeader className="items-center">
                <Badge variant="secondary" className="mb-2">
                  {t("pricing.comingSoon")}
                </Badge>
                <CardTitle>{t("pricing.title")}</CardTitle>
                <CardDescription>{t("pricing.subtitle")}</CardDescription>
              </CardHeader>
            </Card>
          </div>
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="mx-auto max-w-6xl px-4 text-center text-sm text-muted-foreground">
          {t("footer.copyright", { year })}
        </div>
      </footer>
    </div>
  );
}
