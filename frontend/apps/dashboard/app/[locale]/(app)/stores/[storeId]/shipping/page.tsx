"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { EmptyState } from "@saas/ui/empty-state";
import { Skeleton } from "@saas/ui/skeleton";
import { Plus, Truck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";

import { AddShippingZoneDialog } from "@/components/add-shipping-zone-dialog";
import { ManageShippingMethodsDialog } from "@/components/manage-shipping-methods-dialog";
import { useShippingZones } from "@/lib/hooks/use-shipping-zones";

export default function ShippingPage() {
  const t = useTranslations("nav");
  const params = useParams<{ storeId: string }>();
  const { data, isLoading } = useShippingZones(params.storeId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("shipping")}</h1>
        <AddShippingZoneDialog
          storeId={params.storeId}
          trigger={
            <Button>
              <Plus className="h-4 w-4" />
              Add zone
            </Button>
          }
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={Truck}
          title="No shipping zones yet"
          description="Add a shipping zone to start quoting rates at checkout."
          action={
            <AddShippingZoneDialog
              storeId={params.storeId}
              trigger={
                <Button>
                  <Plus className="h-4 w-4" />
                  Add your first zone
                </Button>
              }
            />
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-start font-medium">Zone</th>
                <th className="px-4 py-2.5 text-start font-medium">Countries</th>
                <th className="px-4 py-2.5 text-start font-medium">Status</th>
                <th className="px-4 py-2.5 text-start font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.map((zone) => (
                <tr key={zone.id} className="border-b last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{zone.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {zone.countries?.join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={zone.is_active ? "success" : "secondary"}>
                      {zone.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-end">
                    <ManageShippingMethodsDialog
                      storeId={params.storeId}
                      zoneId={zone.id ?? ""}
                      zoneName={zone.name}
                      trigger={
                        <Button variant="outline" size="sm">
                          Manage methods
                        </Button>
                      }
                    />
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
