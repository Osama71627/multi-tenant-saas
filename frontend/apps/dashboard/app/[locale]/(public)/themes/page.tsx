import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@saas/ui/card";
import { Eye, Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { cairoDisplay, playfairDisplay } from "@/lib/marketplace-fonts";
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

// A subtle diagonal crosshatch, the same "give a plain white page some
// texture without a loud gradient" trick used across the modern-saas
// design skill's own hero/pricing sections -- kept extremely faint
// (5% stroke opacity) since this is a product page people browse
// slowly, not a landing page meant to be seen once.
const DIAGONAL_PATTERN =
  "url(\"data:image/svg+xml,%3Csvg width='24' height='24' viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0l24 24M24 0L0 24' stroke='%23000000' stroke-opacity='0.05' stroke-width='1'/%3E%3C/svg%3E\")";

/**
 * The public Theme Marketplace (Phase B of the "product vision reset")
 * -- genuinely unauthenticated, backed by `GET /api/v1/themes/public/
 * presets`. Each card's "preview swatch" is the theme's own real
 * primary/secondary/accent colors rendered as a small gradient, not a
 * fabricated screenshot -- there's no screenshot pipeline in this
 * project, and an honest color/style indicator beats a fake image.
 *
 * Visual redesign: the original layout was functionally complete but
 * looked like an unstyled admin table (flat header, no visual
 * hierarchy, a bare functional grid) -- this is the platform's own
 * merchant-facing storefront, its most important first impression.
 * Restyled around a few concrete moves, not a wholesale rebrand of the
 * dashboard (deliberately left @saas/ui's own Button/Card/Badge colors
 * untouched everywhere else): an editorial display heading (Playfair
 * Display for `en`, a bold Cairo treatment for `ar` -- Playfair has no
 * Arabic glyphs, see lib/marketplace-fonts.ts's own comment on why
 * that split exists rather than one silently degrading), an eyebrow
 * label, a faint background texture, and real card polish (a floated
 * category badge over the swatch instead of a second header row,
 * hover lift + shadow + swatch zoom, a shared border-radius language
 * with the rest of the app).
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

  const displayFont = locale === "ar" ? cairoDisplay : playfairDisplay;

  return (
    <div className="relative overflow-hidden bg-background">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: DIAGONAL_PATTERN }}
      />
      <div className="relative mx-auto max-w-6xl px-4 py-20">
        <div className="mb-14 flex flex-col items-center text-center">
          <span className="mb-5 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3.5 py-1.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
            <Sparkles className="h-3.5 w-3.5" />
            {t("eyebrow")}
          </span>
          <h1 className={`${displayFont.className} text-4xl font-bold tracking-tight sm:text-5xl`}>
            {t("title")}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>

        {presets.length === 0 ? (
          <p className="text-center text-muted-foreground">{t("empty")}</p>
        ) : (
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {presets.map((preset) => {
              const settings = preset.default_settings;
              return (
                <Card
                  key={preset.id}
                  className="group flex flex-col overflow-hidden border-border/70 transition-all duration-300 hover:-translate-y-1 hover:border-emerald-200 hover:shadow-xl dark:hover:border-emerald-900"
                >
                  <div className="relative h-44 overflow-hidden">
                    <div
                      className="absolute inset-0 transition-transform duration-500 ease-out group-hover:scale-105"
                      style={{
                        background: `linear-gradient(135deg, ${settings.primary_color}, ${settings.secondary_color} 60%, ${settings.accent_color})`,
                      }}
                    />
                    <Badge
                      variant="secondary"
                      className="absolute start-3 top-3 border-0 bg-white/90 text-foreground shadow-sm backdrop-blur-sm"
                    >
                      {preset.theme_category}
                    </Badge>
                  </div>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">{preset.theme_name}</CardTitle>
                    <CardDescription>{settings.hero_subheadline}</CardDescription>
                  </CardHeader>
                  <CardContent className="mt-auto flex gap-2 pt-0">
                    <Button asChild variant="outline" className="flex-1">
                      <Link href={`/${locale}/themes/${preset.id}/preview`}>
                        <Eye className="h-4 w-4" />
                        {t("preview")}
                      </Link>
                    </Button>
                    <Button asChild className="flex-1">
                      {/* Carries the PRESET id, not the theme code -- Phase D's
                          checkout session stores this opaquely and the frontend
                          resolves it back to a name/preview via the same public
                          preset list, so an id is unambiguous even if a theme
                          ever has more than one active preset. */}
                      <Link href={`/${locale}/register?theme=${preset.id}`}>{t("useTheme")}</Link>
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
