import type { components } from "@saas/api-client";

import { serverStorefrontApi } from "@/lib/backend";

export type StorefrontProductListItem = components["schemas"]["StorefrontProductList"];
export type StorefrontProductDetail = components["schemas"]["StorefrontProductDetail"];
export type StorefrontCategory = components["schemas"]["StorefrontCategory"];

export async function getProducts(
  hostname: string,
  categorySlug?: string
): Promise<StorefrontProductListItem[]> {
  const api = serverStorefrontApi(hostname);
  const { data, error } = await api.GET("/api/v1/storefront/products", {
    params: { query: categorySlug ? { category: categorySlug } : undefined },
  });
  if (error || !data) return [];
  return data;
}

export async function getProduct(
  hostname: string,
  slug: string
): Promise<StorefrontProductDetail | null> {
  const api = serverStorefrontApi(hostname);
  const { data, error } = await api.GET("/api/v1/storefront/products/{slug}", {
    params: { path: { slug } },
  });
  if (error || !data) return null;
  return data;
}

export async function getCategories(hostname: string): Promise<StorefrontCategory[]> {
  const api = serverStorefrontApi(hostname);
  const { data, error } = await api.GET("/api/v1/storefront/categories");
  if (error || !data) return [];
  return data;
}
