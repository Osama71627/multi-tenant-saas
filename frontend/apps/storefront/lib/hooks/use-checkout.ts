"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { clientStorefrontApi } from "@/lib/backend";
import type { components } from "@saas/api-client";

type ProviderKey = components["schemas"]["ProviderKeyEnum"];

export function useStartCheckout() {
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await clientStorefrontApi().POST(
        "/api/v1/storefront/checkout/start"
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useSetCheckoutAddress() {
  return useMutation({
    mutationFn: async (input: {
      email: string;
      shipping_address: {
        recipient_name: string;
        phone: string;
        country_code: string;
        region: string;
        city: string;
        postal_code: string;
        line1: string;
        line2: string;
      };
    }) => {
      const { data, error } = await clientStorefrontApi().POST(
        "/api/v1/storefront/checkout/address",
        { body: input }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useShippingQuotes(params: {
  country_code: string;
  region?: string;
  postal_code?: string;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: ["shipping-quotes", params.country_code, params.region, params.postal_code],
    enabled: params.enabled && Boolean(params.country_code),
    queryFn: async () => {
      const { data, error } = await clientStorefrontApi().GET(
        "/api/v1/storefront/cart/shipping-quotes",
        {
          params: {
            query: {
              country_code: params.country_code,
              region: params.region ?? "",
              postal_code: params.postal_code ?? "",
            },
          },
        }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useSetCheckoutShipping() {
  return useMutation({
    mutationFn: async (shippingMethodId: string) => {
      const { data, error } = await clientStorefrontApi().POST(
        "/api/v1/storefront/checkout/shipping",
        { body: { shipping_method_id: shippingMethodId } }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function usePaymentProviders() {
  return useQuery({
    queryKey: ["payment-providers"],
    queryFn: async () => {
      const { data, error } = await clientStorefrontApi().GET(
        "/api/v1/storefront/payments/providers"
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useCompleteCheckout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (idempotencyKey: string) => {
      const { data, error } = await clientStorefrontApi().POST(
        "/api/v1/storefront/checkout/complete",
        { headers: { "Idempotency-Key": idempotencyKey } }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cart"] });
    },
  });
}

export function useInitiatePayment() {
  return useMutation({
    mutationFn: async (input: {
      orderId: string;
      providerKey: ProviderKey;
      idempotencyKey: string;
    }) => {
      const { data, error } = await clientStorefrontApi().POST(
        "/api/v1/storefront/payments/initiate",
        {
          headers: { "Idempotency-Key": input.idempotencyKey },
          body: { order_id: input.orderId, provider_key: input.providerKey },
        }
      );
      if (error) throw error;
      return data;
    },
  });
}
