"use client";

import { Badge } from "@saas/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Separator } from "@saas/ui/separator";
import { Skeleton } from "@saas/ui/skeleton";
import Link from "next/link";
import { useParams } from "next/navigation";

import { formatMoney } from "@/lib/format-money";
import { useOrder } from "@/lib/hooks/use-orders";

const STATUS_VARIANT: Record<string, "success" | "secondary" | "warning" | "destructive"> = {
  confirmed: "success",
  pending_payment: "warning",
  cancelled: "destructive",
};

interface ShippingAddress {
  recipient_name: string;
  phone: string;
  country_code: string;
  region?: string;
  city: string;
  postal_code?: string;
  line1: string;
  line2?: string;
}

function isShippingAddress(value: unknown): value is ShippingAddress {
  return Boolean(value && typeof value === "object" && "recipient_name" in value);
}

export default function OrderDetailPage() {
  const params = useParams<{ storeId: string; orderId: string; locale: string }>();
  const { data: order, isLoading } = useOrder(params.storeId, params.orderId);

  if (isLoading || !order) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const address = isShippingAddress(order.shipping_address) ? order.shipping_address : null;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/${params.locale}/stores/${params.storeId}/orders`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Orders
        </Link>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Order {order.number}</h1>
          <Badge variant={STATUS_VARIANT[order.status ?? ""] ?? "secondary"}>{order.status}</Badge>
          <Badge variant="secondary">{order.fulfillment_status}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Placed {new Date(order.created_at).toLocaleString()}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-hidden rounded-lg border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40 text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2.5 text-start font-medium">Item</th>
                    <th className="px-4 py-2.5 text-start font-medium">SKU</th>
                    <th className="px-4 py-2.5 text-end font-medium">Qty</th>
                    <th className="px-4 py-2.5 text-end font-medium">Unit price</th>
                    <th className="px-4 py-2.5 text-end font-medium">Line total</th>
                  </tr>
                </thead>
                <tbody>
                  {order.items?.map((item) => (
                    <tr key={item.id} className="border-b last:border-0">
                      <td className="px-4 py-3 font-medium">{item.variant_name_snapshot}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {item.variant_sku_snapshot}
                      </td>
                      <td className="px-4 py-3 text-end">{item.quantity}</td>
                      <td className="px-4 py-3 text-end">
                        {formatMoney(item.unit_price_amount, item.currency)}
                      </td>
                      <td className="px-4 py-3 text-end">
                        {formatMoney(item.line_total_amount, item.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Customer</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{order.email}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Shipping</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              {order.shipping_method_name_snapshot ? (
                <p className="font-medium">{order.shipping_method_name_snapshot}</p>
              ) : (
                <p className="text-muted-foreground">No shipping method</p>
              )}
              {address ? (
                <div className="text-muted-foreground">
                  <p>{address.recipient_name}</p>
                  <p>{address.line1}</p>
                  {address.line2 ? <p>{address.line2}</p> : null}
                  <p>
                    {address.city}
                    {address.region ? `, ${address.region}` : ""} {address.postal_code}
                  </p>
                  <p>{address.country_code}</p>
                  <p>{address.phone}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Totals</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Subtotal</span>
                <span>{formatMoney(order.subtotal_amount, order.currency)}</span>
              </div>
              {order.discount_amount > 0 ? (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Discount{order.coupon_code_snapshot ? ` (${order.coupon_code_snapshot})` : ""}
                  </span>
                  <span>-{formatMoney(order.discount_amount, order.currency)}</span>
                </div>
              ) : null}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Shipping</span>
                <span>{formatMoney(order.shipping_amount, order.currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tax</span>
                <span>{formatMoney(order.tax_amount, order.currency)}</span>
              </div>
              <Separator className="my-1" />
              <div className="flex justify-between font-medium">
                <span>Total</span>
                <span>{formatMoney(order.total_amount, order.currency)}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
