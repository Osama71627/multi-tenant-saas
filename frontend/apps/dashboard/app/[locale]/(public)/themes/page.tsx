import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@saas/ui/card";
import { Eye } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { serverFetch } from "@/lib/session";

interface ThemeSettings {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  hero_subheadline: string;
}

interface PublicThemePreset {
  id: string;
  name: string;
  default_settings: ThemeSettings;
  preview_image_url: string;
  theme_code: string;
  theme_name: string;
  theme_category: string;
}

/**
 * The public Theme Marketplace (Phase B of the "product vision reset")
 * -- genuinely unauthenticated, backed by `GET /api/v1/themes/public/
 * presets`. Each card's "preview swatch" is the theme's own real
 * primary/secondary/accent colors rendered as a small gradient, not a
 * fabricated screenshot -- there's no screenshot pipeline in this
 * project, and an honest color/style indicator beats a fake image.
 */
export default async function ThemeMarketplacePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("themesMarketplace");

  const response = await serverFetch("api/v1/themes/public/presets");
  const presets: PublicThemePreset[] = response.ok ? await response.json() : [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <div className="mb-12 text-center">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">{t("subtitle")}</p>
      </div>

      {presets.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {presets.map((preset) => {
            const settings = preset.default_settings;
            return (
              <Card key={preset.id} className="flex flex-col overflow-hidden">
                <div
                  className="h-40"
                  style={{
                    background: `linear-gradient(135deg, ${settings.primary_color}, ${settings.secondary_color} 60%, ${settings.accent_color})`,
                  }}
                />
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{preset.theme_name}</CardTitle>
                    <Badge variant="secondary">{preset.theme_category}</Badge>
                  </div>
                  <CardDescription>{settings.hero_subheadline}</CardDescription>
                </CardHeader>
                <CardContent className="mt-auto flex gap-2">
                  <Button asChild variant="outline" className="flex-1">
                    <Link href={`/${locale}/themes/${preset.id}/preview`}>
                      <Eye className="h-4 w-4" />
                      {t("preview")}
                    </Link>
                  </Button>
                  <Button asChild className="flex-1">
                    <Link href={`/${locale}/register?theme=${preset.theme_code}`}>
                      {t("useTheme")}
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
