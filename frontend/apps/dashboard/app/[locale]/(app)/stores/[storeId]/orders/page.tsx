"use client";

import { Badge } from "@saas/ui/badge";
import { EmptyState } from "@saas/ui/empty-state";
import { Skeleton } from "@saas/ui/skeleton";
import { ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";

import { formatMoney } from "@/lib/format-money";
import { useOrders } from "@/lib/hooks/use-orders";

const STATUS_VARIANT: Record<string, "success" | "secondary" | "warning" | "destructive"> = {
  confirmed: "success",
  pending_payment: "warning",
  cancelled: "destructive",
};

export default function OrdersPage() {
  const t = useTranslations("nav");
  const params = useParams<{ storeId: string; locale: string }>();
  const { data, isLoading } = useOrders(params.storeId);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t("orders")}</h1>

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={ShoppingCart}
          title="No orders yet"
          description="Once customers start checking out, their orders will show up here."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-start font-medium">Order</th>
                <th className="px-4 py-2.5 text-start font-medium">Customer</th>
                <th className="px-4 py-2.5 text-start font-medium">Status</th>
                <th className="px-4 py-2.5 text-start font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.map((order) => (
                <tr key={order.id} className="border-b last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">
                    <Link
                      href={`/${params.locale}/stores/${params.storeId}/orders/${order.id}`}
                      className="hover:underline"
                    >
                      {order.number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{order.email}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANT[order.status ?? ""] ?? "secondary"}>
                      {order.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">{formatMoney(order.total_amount, order.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
