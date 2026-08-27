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
 * Mirrors apps/storefront/components/theme-registry.tsx exactly, same
 * real theme packages -- live preview renders with the real theme
 * components, never a second/fake preview UI.
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
} as const;

export function getTheme(code: string) {
  return THEMES[code as keyof typeof THEMES] ?? THEMES.aurora;
}

/** Each theme package exports its own identically-shaped `xCssVars`
 * function (see e.g. @saas/theme-fashion/src/theme-vars.ts's own note
 * on why these are duplicated per theme, not shared) -- this dispatches
 * by code the same way `getTheme` does, so callers rendering ANY
 * theme's settings (the public marketplace preview, the per-store live
 * preview) don't need their own switch statement. `AuroraSettings`'s
 * shape is shared by every theme's settings contract (see
 * backend/apps/themes/schemas.py's comment), so one parameter type
 * covers all four. */
export function getCssVars(code: string, settings: AuroraSettings): CSSProperties {
  switch (code as keyof typeof THEMES) {
    case "fashion":
      return fashionCssVars(settings);
    case "electronics":
      return electronicsCssVars(settings);
    case "luxury":
      return luxuryCssVars(settings);
    default:
      return auroraCssVars(settings);
  }
}
