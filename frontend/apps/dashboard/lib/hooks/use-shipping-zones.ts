"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import type { components } from "@saas/api-client";

export function useShippingZones(storeId: string) {
  return useQuery({
    queryKey: ["shipping-zones", storeId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/dashboard/stores/{store_id}/shipping/zones", {
        params: { path: { store_id: storeId } },
      });
      if (error) throw error;
      return data;
    },
  });
}

export function useCreateShippingZone(storeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: components["schemas"]["ShippingZoneRequest"]) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/shipping/zones",
        { params: { path: { store_id: storeId } }, body: input }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shipping-zones", storeId] });
    },
  });
}

export function useShippingMethods(storeId: string, zoneId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["shipping-methods", storeId, zoneId],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone_id}/methods",
        { params: { path: { store_id: storeId, zone_id: zoneId } } }
      );
      if (error) throw error;
      return data;
    },
  });
}

export function useCreateShippingMethod(storeId: string, zoneId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Omit<components["schemas"]["ShippingMethodRequest"], "zone">) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone_id}/methods",
        {
          params: { path: { store_id: storeId, zone_id: zoneId } },
          body: { ...input, zone: zoneId },
        }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shipping-methods", storeId, zoneId] });
    },
  });
}

export function useCreateShippingRate(storeId: string, zoneId: string, methodId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Omit<components["schemas"]["ShippingRateRequest"], "method">) => {
      const { data, error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/shipping/methods/{method_id}/rates",
        {
          params: { path: { store_id: storeId, method_id: methodId } },
          body: { ...input, method: methodId },
        }
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shipping-methods", storeId, zoneId] });
    },
  });
}
