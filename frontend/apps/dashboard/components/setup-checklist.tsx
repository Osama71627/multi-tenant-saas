"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Skeleton } from "@saas/ui/skeleton";
import { useQueries } from "@tanstack/react-query";
import { Check, Circle, Store as StoreIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { api } from "@/lib/api-client";
import { useStockBalances } from "@/lib/hooks/use-inventory";
import { usePaymentProviders } from "@/lib/hooks/use-payment-providers";
import { useProducts } from "@/lib/hooks/use-products";
import { useShippingZones } from "@/lib/hooks/use-shipping-zones";
import { useStore } from "@/lib/hooks/use-store";
import { storefrontUrl } from "@/lib/storefront-url";

interface ChecklistItem {
  label: string;
  done: boolean;
  href: string;
}

export function SetupChecklist({ storeId }: { storeId: string }) {
  const { locale } = useParams<{ locale: string }>();
  const base = `/${locale}/stores/${storeId}`;

  const { data: store, isLoading: storeLoading } = useStore(storeId);
  const { data: products, isLoading: productsLoading } = useProducts(storeId);
  const { data: balances, isLoading: balancesLoading } = useStockBalances(storeId);
  const { data: zones, isLoading: zonesLoading } = useShippingZones(storeId);
  const { data: providers, isLoading: providersLoading } = usePaymentProviders(storeId);

  // A zone alone doesn't let checkout quote a price -- it needs at least
  // one method (see the Shipping write-slice chunk). Reading each zone's
  // methods is still a direct read of existing authoritative data (no
  // new backend endpoint, no frontend-computed truth), just N small
  // GETs instead of one.
  const methodQueries = useQueries({
    queries: (zones ?? []).map((zone) => ({
      queryKey: ["shipping-methods", storeId, zone.id],
      queryFn: async () => {
        const { data, error } = await api.GET(
          "/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone_id}/methods",
          { params: { path: { store_id: storeId, zone_id: zone.id ?? "" } } }
        );
        if (error) throw error;
        return data;
      },
      enabled: Boolean(zones?.length),
    })),
  });
  const methodsLoading = zonesLoading || (Boolean(zones?.length) && methodQueries.some((q) => q.isLoading));
  const hasConfiguredShipping =
    (zones?.length ?? 0) > 0 && methodQueries.some((q) => (q.data?.length ?? 0) > 0);

  const isLoading =
    storeLoading || productsLoading || balancesLoading || methodsLoading || providersLoading;

  const items: ChecklistItem[] = [
    {
      label: "Store details complete",
      done: Boolean(store?.contact_email),
      href: `${base}/settings`,
    },
    {
      label: "At least one active product",
      done: (products ?? []).some((p) => p.status === "active"),
      href: `${base}/products`,
    },
    {
      label: "Inventory available",
      done: (balances ?? []).some((b) => (b.quantity_available ?? 0) > 0),
      href: `${base}/inventory`,
    },
    {
      label: "Shipping configured",
      done: hasConfiguredShipping,
      href: `${base}/shipping`,
    },
    {
      label: "Payment provider connected",
      done: (providers ?? []).some((p) => p.is_enabled),
      href: `${base}/payments`,
    },
  ];

  const doneCount = items.filter((item) => item.done).length;
  const allDone = !isLoading && doneCount === items.length;
  const nextItem = items.find((item) => !item.done);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Launch readiness</CardTitle>
        {!isLoading ? (
          <Badge variant={allDone ? "success" : "secondary"}>
            {doneCount}/{items.length}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <>
            {allDone ? (
              <p className="text-sm text-emerald-600">
                Everything&apos;s set up. Your store is ready to launch.
              </p>
            ) : nextItem ? (
              <div className="flex items-center justify-between rounded-md bg-accent/50 px-3 py-2">
                <p className="text-sm">
                  Next: <span className="font-medium">{nextItem.label}</span>
                </p>
                <Button asChild size="sm" variant="outline">
                  <Link href={nextItem.href}>Go</Link>
                </Button>
              </div>
            ) : null}

            <ul className="space-y-1">
              {items.map((item) => (
                <li key={item.label}>
                  <Link
                    href={item.href}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                  >
                    {item.done ? (
                      <Check className="h-4 w-4 shrink-0 text-emerald-600" />
                    ) : (
                      <Circle className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className={item.done ? "text-muted-foreground line-through" : ""}>
                      {item.label}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>

            <div className="flex items-center justify-between border-t pt-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <StoreIcon className="h-4 w-4" />
                Live storefront preview
              </div>
              {/* Real gap found live: this used to always open the
                  internal fixture-data preview at `${base}/preview`
                  (demo products, not this merchant's real catalog) --
                  misleading once a store actually has real products, as
                  this one does. Opens the merchant's own real storefront
                  in a new tab now that `store.primary_domain` exists;
                  falls back to the fixture preview only in the genuinely
                  impossible case of a Store with no primary domain row. */}
              <Button asChild size="sm" variant="outline">
                {store?.primary_domain ? (
                  <a href={storefrontUrl(store.primary_domain)} target="_blank" rel="noopener noreferrer">
                    Preview store
                  </a>
                ) : (
                  <Link href={`${base}/preview`}>Preview store</Link>
                )}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
