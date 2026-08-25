/**
 * Mirrors `backend/apps/themes/schemas.py:AuroraV1SettingsSerializer`
 * exactly -- the (theme_code="aurora", version=1) contract. A future
 * ThemeVersion would need its own settings type + component set;
 * nothing here is generic across themes on purpose.
 */
export interface AuroraSettings {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_choice: "inter" | "cairo" | "tajawal";
  hero_headline: string;
  hero_subheadline: string;
  homepage_sections: Array<"hero" | "featured_products" | "categories" | "newsletter">;
  nav_order: Array<"shop" | "about" | "contact">;
}

export interface AuroraProductListItem {
  id: string;
  name: string;
  slug: string;
  price_amount: number | null;
  currency: string | null;
  compare_at_price_amount?: number | null;
}

export interface AuroraCategory {
  id: string;
  name: string;
  slug: string;
}
