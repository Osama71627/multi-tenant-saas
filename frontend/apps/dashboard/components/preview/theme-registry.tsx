import {
  AuroraCategoriesSection,
  AuroraFeaturedProducts,
  AuroraFooter,
  AuroraHeader,
  AuroraHero,
  AuroraNewsletter,
  AuroraProductCard,
} from "@saas/theme-aurora";

/**
 * Mirrors apps/storefront/components/theme-registry.tsx exactly, same
 * `@saas/theme-aurora` package -- live preview renders with the real
 * theme components, never a second/fake preview UI.
 */
const THEMES = {
  aurora: {
    Header: AuroraHeader,
    Footer: AuroraFooter,
    Hero: AuroraHero,
    FeaturedProducts: AuroraFeaturedProducts,
    Categories: AuroraCategoriesSection,
    Newsletter: AuroraNewsletter,
    ProductCard: AuroraProductCard,
  },
} as const;

export function getTheme(code: string) {
  return THEMES[code as keyof typeof THEMES] ?? THEMES.aurora;
}
