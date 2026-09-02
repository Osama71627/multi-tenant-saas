/**
 * Mirrors `backend/apps/themes/schemas.py`'s `("homestore", 1)` contract
 * -- deliberately the SAME shape as every other theme's (see that
 * module's own comment: the settings contract a merchant configures is
 * shared across themes; what a theme changes is the RENDERING, in each
 * theme's own component package). Duplicated rather than imported from
 * another theme package on purpose, matching that same precedent.
 */
export interface HomestoreSettings {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_choice: "inter" | "cairo" | "tajawal";
  hero_headline: string;
  hero_subheadline: string;
  homepage_sections: Array<"hero" | "featured_products" | "categories" | "newsletter">;
  nav_order: Array<"shop" | "about" | "contact">;
}

export interface HomestoreProductListItem {
  id: string;
  name: string;
  slug: string;
  price_amount: number | null;
  currency: string | null;
  compare_at_price_amount?: number | null;
  /**
   * Deliberately OPTIONAL and never populated by any real backend
   * response -- `apps.catalog.models.Product`/`ProductVariant` have no
   * image field at all yet (a real, separate, not-yet-built feature).
   * Exists here purely so the dashboard's own live-preview/marketplace-
   * preview fixtures (see apps/dashboard/components/preview/
   * fixture-catalog.ts's HOMESTORE_FIXTURE_PRODUCTS) can show this
   * theme with real photography instead of a placeholder, WITHOUT ever
   * misrepresenting a real merchant's actual (currently photo-less)
   * catalog -- HomestoreProductCard falls back to the same considered
   * gradient-placeholder treatment every other theme uses whenever this
   * is unset, which is always, for any real product today.
   */
  image_url?: string | null;
}

export interface HomestoreCategory {
  id: string;
  name: string;
  slug: string;
  /** See HomestoreProductListItem.image_url's own comment -- same
   * fixture-only honesty rule (`apps.catalog.models.Category` has no
   * image field either). */
  image_url?: string | null;
}
