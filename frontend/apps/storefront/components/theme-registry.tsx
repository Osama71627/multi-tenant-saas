import {
  AuroraCategoriesSection,
  AuroraFeaturedProducts,
  AuroraFooter,
  AuroraHeader,
  AuroraHero,
  AuroraNewsletter,
  AuroraProductCard,
  AuroraProductGrid,
  auroraCssVars,
  type AuroraSettings,
} from "@saas/theme-aurora";
import {
  ElectronicsCategoriesSection,
  ElectronicsFeaturedProducts,
  ElectronicsFooter,
  ElectronicsHeader,
  ElectronicsHero,
  ElectronicsNewsletter,
  ElectronicsProductCard,
  ElectronicsProductGrid,
  electronicsCssVars,
} from "@saas/theme-electronics";
import {
  FashionCategoriesSection,
  FashionFeaturedProducts,
  FashionFooter,
  FashionHeader,
  FashionHero,
  FashionNewsletter,
  FashionProductCard,
  FashionProductGrid,
  fashionCssVars,
} from "@saas/theme-fashion";
import {
  HomestoreCategoriesSection,
  HomestoreFeaturedProducts,
  HomestoreFooter,
  HomestoreHeader,
  HomestoreHero,
  HomestoreNewsletter,
  HomestoreProductCard,
  HomestoreProductGrid,
  homestoreCssVars,
} from "@saas/theme-homestore";
import {
  LuxuryCategoriesSection,
  LuxuryFeaturedProducts,
  LuxuryFooter,
  LuxuryHeader,
  LuxuryHero,
  LuxuryNewsletter,
  LuxuryProductCard,
  LuxuryProductGrid,
  luxuryCssVars,
} from "@saas/theme-luxury";
import type { CSSProperties } from "react";

/**
 * `Theme.code` -> the real, shared component package for that theme
 * (approved architecture: "maps to real storefront component package/
 * renderer"). Phase B ("product vision reset" theme marketplace) adds
 * three genuinely distinct themes alongside Aurora -- each its own
 * package with its own layout/typography/component design, not a
 * palette variation of Aurora. An unknown/future code still falls back
 * to Aurora rather than crashing the page -- a store can never end up
 * with literally nothing to render. The dashboard's live-preview
 * registry (apps/dashboard/components/preview/theme-registry.tsx)
 * mirrors this exact same set of packages, so there is only ever one
 * component set per theme.
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
    ProductGrid: AuroraProductGrid,
  },
  fashion: {
    Header: FashionHeader,
    Footer: FashionFooter,
    Hero: FashionHero,
    FeaturedProducts: FashionFeaturedProducts,
    Categories: FashionCategoriesSection,
    Newsletter: FashionNewsletter,
    ProductCard: FashionProductCard,
    ProductGrid: FashionProductGrid,
  },
  electronics: {
    Header: ElectronicsHeader,
    Footer: ElectronicsFooter,
    Hero: ElectronicsHero,
    FeaturedProducts: ElectronicsFeaturedProducts,
    Categories: ElectronicsCategoriesSection,
    Newsletter: ElectronicsNewsletter,
    ProductCard: ElectronicsProductCard,
    ProductGrid: ElectronicsProductGrid,
  },
  luxury: {
    Header: LuxuryHeader,
    Footer: LuxuryFooter,
    Hero: LuxuryHero,
    FeaturedProducts: LuxuryFeaturedProducts,
    Categories: LuxuryCategoriesSection,
    Newsletter: LuxuryNewsletter,
    ProductCard: LuxuryProductCard,
    ProductGrid: LuxuryProductGrid,
  },
  homestore: {
    Header: HomestoreHeader,
    Footer: HomestoreFooter,
    Hero: HomestoreHero,
    FeaturedProducts: HomestoreFeaturedProducts,
    Categories: HomestoreCategoriesSection,
    Newsletter: HomestoreNewsletter,
    ProductCard: HomestoreProductCard,
    ProductGrid: HomestoreProductGrid,
  },
} as const;

export function getTheme(code: string) {
  return THEMES[code as keyof typeof THEMES] ?? THEMES.aurora;
}

/** Mirrors apps/dashboard/components/preview/theme-registry.tsx's
 * identical helper -- dispatches to whichever theme's own `xCssVars`
 * function by code, same shared-settings-shape rationale. */
export function getCssVars(code: string, settings: AuroraSettings): CSSProperties {
  switch (code as keyof typeof THEMES) {
    case "fashion":
      return fashionCssVars(settings);
    case "electronics":
      return electronicsCssVars(settings);
    case "luxury":
      return luxuryCssVars(settings);
    case "homestore":
      return homestoreCssVars(settings);
    default:
      return auroraCssVars(settings);
  }
}
