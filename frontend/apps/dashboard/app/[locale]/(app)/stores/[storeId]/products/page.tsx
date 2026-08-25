"use client";

import { Button } from "@saas/ui/button";
import { EmptyState } from "@saas/ui/empty-state";
import { Skeleton } from "@saas/ui/skeleton";
import { Package, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";

import { AddProductDialog } from "@/components/add-product-dialog";
import { ProductStatusSelect } from "@/components/product-status-select";
import { useProducts } from "@/lib/hooks/use-products";

export default function ProductsPage() {
  const t = useTranslations("nav");
  const params = useParams<{ storeId: string }>();
  const { data, isLoading } = useProducts(params.storeId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("products")}</h1>
        <AddProductDialog
          storeId={params.storeId}
          trigger={
            <Button>
              <Plus className="h-4 w-4" />
              Add product
            </Button>
          }
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={Package}
          title="No products yet"
          description="Products you add will show up here, ready to sell as soon as your store launches."
          action={
            <AddProductDialog
              storeId={params.storeId}
              trigger={
                <Button>
                  <Plus className="h-4 w-4" />
                  Add your first product
                </Button>
              }
            />
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-start text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-start font-medium">Name</th>
                <th className="px-4 py-2.5 text-start font-medium">Status</th>
                <th className="px-4 py-2.5 text-start font-medium">Variants</th>
              </tr>
            </thead>
            <tbody>
              {data.map((product) => (
                <tr key={product.id} className="border-b last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{product.name}</td>
                  <td className="px-4 py-3">
                    <ProductStatusSelect
                      storeId={params.storeId}
                      productId={product.id ?? ""}
                      status={product.status ?? "draft"}
                    />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{product.variants?.length ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
