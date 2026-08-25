"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { EmptyState } from "@saas/ui/empty-state";
import { Skeleton } from "@saas/ui/skeleton";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { MapPin, Plus, Warehouse } from "lucide-react";

import { AddLocationDialog } from "@/components/add-location-dialog";
import { AdjustStockDialog } from "@/components/adjust-stock-dialog";
import { useStockBalances } from "@/lib/hooks/use-inventory";

export default function InventoryPage() {
  const t = useTranslations("nav");
  const params = useParams<{ storeId: string }>();
  const { data, isLoading } = useStockBalances(params.storeId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("inventory")}</h1>
        <div className="flex gap-2">
          <AddLocationDialog
            storeId={params.storeId}
            trigger={
              <Button variant="outline">
                <MapPin className="h-4 w-4" />
                Add location
              </Button>
            }
          />
          <AdjustStockDialog
            storeId={params.storeId}
            trigger={
              <Button>
                <Plus className="h-4 w-4" />
                Adjust stock
              </Button>
            }
          />
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={Warehouse}
          title="No stock tracked yet"
          description="Stock balances will appear here once you add products and locations."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-start font-medium">SKU</th>
                <th className="px-4 py-2.5 text-start font-medium">Location</th>
                <th className="px-4 py-2.5 text-start font-medium">On hand</th>
                <th className="px-4 py-2.5 text-start font-medium">Reserved</th>
                <th className="px-4 py-2.5 text-start font-medium">Available</th>
              </tr>
            </thead>
            <tbody>
              {data.map((balance) => (
                <tr key={balance.id} className="border-b last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{balance.variant_sku}</td>
                  <td className="px-4 py-3 text-muted-foreground">{balance.location_name}</td>
                  <td className="px-4 py-3">{balance.quantity_on_hand}</td>
                  <td className="px-4 py-3">{balance.quantity_reserved}</td>
                  <td className="px-4 py-3">
                    {balance.is_low_stock ? (
                      <Badge variant="warning">{balance.quantity_available} low</Badge>
                    ) : (
                      balance.quantity_available
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
