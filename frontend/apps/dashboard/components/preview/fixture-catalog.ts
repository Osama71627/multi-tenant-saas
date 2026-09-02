import type { AuroraCategory, AuroraProductListItem } from "@saas/theme-aurora";
import type { HomestoreCategory, HomestoreProductListItem } from "@saas/theme-homestore";

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

/**
 * HomeStore-only fixtures, with real product photography -- a real,
 * complete storefront design the user brought (github.com/Osama71627/
 * Online_shop) included real photos; used here ONLY in this
 * preview-fixture context (never on a real merchant's actual
 * storefront, which always renders real -- currently photo-less --
 * catalog data, see HomestoreProductListItem.image_url's own comment)
 * so this theme's preview shows what it looks like with real
 * photography instead of the placeholder art every real store gets
 * until a product-image upload pipeline exists (a separate, not-yet-
 * built feature). Resized/compressed from the original ~12-16MB camera
 * files down to ~200KB JPEGs before being committed here.
 */
export const HOMESTORE_FIXTURE_PRODUCTS: HomestoreProductListItem[] = [
  {
    id: "fixture-hs-1",
    name: "Gilded Glassware Set",
    slug: "gilded-glassware-set",
    price_amount: 8900,
    currency: "USD",
    compare_at_price_amount: null,
    image_url: "/fixtures/homestore/products/082a5119.jpg",
  },
  {
    id: "fixture-hs-2",
    name: "Ornate Tea Service",
    slug: "ornate-tea-service",
    price_amount: 6500,
    currency: "USD",
    compare_at_price_amount: 7900,
    image_url: "/fixtures/homestore/products/082a5159.jpg",
  },
  {
    id: "fixture-hs-3",
    name: "Gold-Rimmed Glass Duo",
    slug: "gold-rimmed-glass-duo",
    price_amount: 3200,
    currency: "USD",
    compare_at_price_amount: null,
    image_url: "/fixtures/homestore/products/082a5249.jpg",
  },
  {
    id: "fixture-hs-4",
    name: "Amber Serving Set",
    slug: "amber-serving-set",
    price_amount: 5400,
    currency: "USD",
    compare_at_price_amount: null,
    image_url: "/fixtures/homestore/products/082a5253.jpg",
  },
  {
    id: "fixture-hs-5",
    name: "Crystal Pitcher Collection",
    slug: "crystal-pitcher-collection",
    price_amount: 7200,
    currency: "USD",
    compare_at_price_amount: 8600,
    image_url: "/fixtures/homestore/products/082a5276.jpg",
  },
  {
    id: "fixture-hs-6",
    name: "Signature Glass Vase",
    slug: "signature-glass-vase",
    price_amount: 4800,
    currency: "USD",
    compare_at_price_amount: null,
    image_url: "/fixtures/homestore/products/product_1.jpg",
  },
];

export const HOMESTORE_FIXTURE_CATEGORIES: HomestoreCategory[] = [
  {
    id: "fixture-hs-cat-1",
    name: "Kitchenware",
    slug: "kitchenware",
    image_url: "/fixtures/homestore/categories/082a5224.jpg",
  },
  {
    id: "fixture-hs-cat-2",
    name: "Tableware",
    slug: "tableware",
    image_url: "/fixtures/homestore/categories/082a5355.jpg",
  },
  {
    id: "fixture-hs-cat-3",
    name: "Drinkware",
    slug: "drinkware",
    image_url: "/fixtures/homestore/categories/082a5357.jpg",
  },
  {
    id: "fixture-hs-cat-4",
    name: "Home Decor",
    slug: "home-decor",
    image_url: "/fixtures/homestore/categories/082a5387.jpg",
  },
  {
    id: "fixture-hs-cat-5",
    name: "Serving Sets",
    slug: "serving-sets",
    image_url: "/fixtures/homestore/categories/082a5393.jpg",
  },
  {
    id: "fixture-hs-cat-6",
    name: "Gift Sets",
    slug: "gift-sets",
    image_url: "/fixtures/homestore/categories/082a5413.jpg",
  },
];
