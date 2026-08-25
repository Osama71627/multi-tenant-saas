"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { EmptyState } from "@saas/ui/empty-state";
import { Skeleton } from "@saas/ui/skeleton";
import { CreditCard, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";

import { ConnectProviderDialog } from "@/components/connect-provider-dialog";
import { usePaymentProviders } from "@/lib/hooks/use-payment-providers";

export default function PaymentsPage() {
  const t = useTranslations("nav");
  const params = useParams<{ storeId: string }>();
  const { data, isLoading } = usePaymentProviders(params.storeId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("payments")}</h1>
        <ConnectProviderDialog
          storeId={params.storeId}
          trigger={
            <Button>
              <Plus className="h-4 w-4" />
              Connect provider
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
          icon={CreditCard}
          title="No payment providers connected"
          description="Connect a payment provider so customers can pay at checkout."
          action={
            <ConnectProviderDialog
              storeId={params.storeId}
              trigger={
                <Button>
                  <Plus className="h-4 w-4" />
                  Connect a provider
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
                <th className="px-4 py-2.5 text-start font-medium">Provider</th>
                <th className="px-4 py-2.5 text-start font-medium">Mode</th>
                <th className="px-4 py-2.5 text-start font-medium">Credentials</th>
                <th className="px-4 py-2.5 text-start font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((config) => (
                <tr key={config.id} className="border-b last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{config.provider_key}</td>
                  <td className="px-4 py-3 text-muted-foreground">{config.mode}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {config.credentials_hint || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={config.is_enabled ? "success" : "secondary"}>
                      {config.is_enabled ? "Enabled" : "Disabled"}
                    </Badge>
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
