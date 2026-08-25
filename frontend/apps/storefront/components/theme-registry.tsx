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
 * `Theme.code` -> the real, shared `@saas/theme-aurora` component set
 * (approved architecture: "maps to real storefront component package/
 * renderer"). Only "aurora" exists today; an unknown/future code falls
 * back to it rather than crashing the page -- a store can never end up
 * with literally nothing to render. The dashboard's live-preview
 * registry (apps/dashboard/components/preview/theme-registry.tsx) picks
 * from this exact same package, so there is only ever one component set.
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
