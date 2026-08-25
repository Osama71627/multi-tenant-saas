import type { AuroraCategory, AuroraProductListItem } from "@saas/theme-aurora";

/**
 * Small bundled/static demo catalog -- approved live-preview scope
 * ("Allowed preview data: small bundled/static demo catalog fixtures.
 * Do NOT create fake production tenants or fake Orders in the real
 * tenant database for preview."). Never fetched from the API, never
 * written anywhere; exists only so the preview's Featured
 * products/Categories sections have something real-looking to render
 * regardless of whether the merchant has added any products yet.
 */
export const FIXTURE_PRODUCTS: AuroraProductListItem[] = [
  {
    id: "fixture-1",
    name: "Classic Tee",
    slug: "classic-tee",
    price_amount: 2500,
    currency: "USD",
    compare_at_price_amount: null,
  },
  {
    id: "fixture-2",
    name: "Canvas Tote",
    slug: "canvas-tote",
    price_amount: 3500,
    currency: "USD",
    compare_at_price_amount: 4500,
  },
  {
    id: "fixture-3",
    name: "Ceramic Mug",
    slug: "ceramic-mug",
    price_amount: 1800,
    currency: "USD",
    compare_at_price_amount: null,
  },
  {
    id: "fixture-4",
    name: "Wool Beanie",
    slug: "wool-beanie",
    price_amount: 2200,
    currency: "USD",
    compare_at_price_amount: null,
  },
];

export const FIXTURE_CATEGORIES: AuroraCategory[] = [
  { id: "fixture-cat-1", name: "Apparel", slug: "apparel" },
  { id: "fixture-cat-2", name: "Accessories", slug: "accessories" },
  { id: "fixture-cat-3", name: "Home", slug: "home" },
];
