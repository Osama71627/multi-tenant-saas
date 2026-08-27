/**
 * Mirrors `backend/apps/themes/schemas.py`'s `("fashion", 1)` contract,
 * which is deliberately the SAME shape as Aurora's (see schemas.py's
 * comment: the settings contract a merchant configures -- color/font/
 * hero copy/section order/nav -- is shared across themes; what a theme
 * actually changes is the RENDERING, in each theme's own component
 * package). Duplicated rather than imported from @saas/theme-aurora on
 * purpose, matching that package's own "nothing generic across themes"
 * precedent: a future FashionV2 settings shape can diverge freely
 * without touching Aurora's type.
 */
export interface FashionSettings {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_choice: "inter" | "cairo" | "tajawal";
  hero_headline: string;
  hero_subheadline: string;
  homepage_sections: Array<"hero" | "featured_products" | "categories" | "newsletter">;
  nav_order: Array<"shop" | "about" | "contact">;
}

export interface FashionProductListItem {
  id: string;
  name: string;
  slug: string;
  price_amount: number | null;
  currency: string | null;
  compare_at_price_amount?: number | null;
}

export interface FashionCategory {
  id: string;
  name: string;
  slug: string;
}
