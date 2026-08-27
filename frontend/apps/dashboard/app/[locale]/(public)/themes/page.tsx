import { Button } from "@saas/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@saas/ui/card";
import { Palette } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

/**
 * Placeholder for the Theme Marketplace -- Phase A only wires the
 * public route (and middleware.ts's PUBLIC_PATH_SEGMENTS) so the
 * landing page's "Explore Themes" CTA has somewhere real to go without
 * a dead link. The real marketplace (multiple browsable/previewable
 * themes, per the approved product vision) is Phase B's scope -- this
 * intentionally does not fabricate theme cards or preview content
 * ahead of that phase.
 */
export default async function ThemesMarketplacePlaceholderPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("themesMarketplace");

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-4 text-center">
      <Card className="w-full">
        <CardHeader className="items-center">
          <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Palette className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>{t("title")}</CardTitle>
          <CardDescription>{t("comingSoonBody")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-3">
          <Button asChild className="w-full">
            <Link href={`/${locale}/register`}>{t("cta")}</Link>
          </Button>
          <Link href={`/${locale}`} className="text-sm text-muted-foreground hover:text-foreground">
            {t("backToHome")}
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
