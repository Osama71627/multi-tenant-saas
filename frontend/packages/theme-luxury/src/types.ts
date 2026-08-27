/** Mirrors `backend/apps/themes/schemas.py`'s `("luxury", 1)` contract
 * -- same shape as Aurora's/Fashion's/Electronics's on purpose (see
 * theme-fashion/src/types.ts's note); duplicated, not shared. */
export interface LuxurySettings {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_choice: "inter" | "cairo" | "tajawal";
  hero_headline: string;
  hero_subheadline: string;
  homepage_sections: Array<"hero" | "featured_products" | "categories" | "newsletter">;
  nav_order: Array<"shop" | "about" | "contact">;
}

export interface LuxuryProductListItem {
  id: string;
  name: string;
  slug: string;
  price_amount: number | null;
  currency: string | null;
  compare_at_price_amount?: number | null;
}

export interface LuxuryCategory {
  id: string;
  name: string;
  slug: string;
}
