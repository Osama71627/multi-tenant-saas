import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { PromoteSupplierProductDialog } from "@/components/promote-supplier-product-dialog";
import { SyncSupplierButton } from "@/components/sync-supplier-button";
import { serverFetch } from "@/lib/session";

interface SupplierProduct {
  id: string;
  external_id: string;
  name: string;
  cost_amount: number;
  currency: string;
  supplier_stock: number;
  status: string;
  suggested_price_amount: number;
}

async function getSupplierProducts(storeId: string, supplierId: string): Promise<SupplierProduct[]> {
  const response = await serverFetch(
    `api/v1/dashboard/stores/${storeId}/suppliers/${supplierId}/products`
  );
  if (!response.ok) return [];
  return response.json();
}

function statusVariant(status: string): "success" | "secondary" | "outline" {
  if (status === "imported") return "success";
  if (status === "ignored") return "outline";
  return "secondary";
}

export default async function SupplierProductsPage({
  params,
}: {
  params: Promise<{ locale: string; storeId: string; supplierId: string }>;
}) {
  const { locale, storeId, supplierId } = await params;
  const t = await getTranslations("suppliers");
  const products = await getSupplierProducts(storeId, supplierId);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/${locale}/stores/${storeId}/suppliers`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← {t("backToSuppliers")}
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("stagedProducts")}</h1>
        <SyncSupplierButton storeId={storeId} supplierId={supplierId} />
      </div>

      {products.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noStagedProducts")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("name")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("cost")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("suggestedPrice")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("supplierStock")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("status")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">{product.name}</td>
                  <td className="px-4 py-2">
                    {(product.cost_amount / 100).toFixed(2)} {product.currency}
                  </td>
                  <td className="px-4 py-2">
                    {(product.suggested_price_amount / 100).toFixed(2)} {product.currency}
                  </td>
                  <td className="px-4 py-2">{product.supplier_stock}</td>
                  <td className="px-4 py-2">
                    <Badge variant={statusVariant(product.status)}>{product.status}</Badge>
                  </td>
                  <td className="px-4 py-2 text-end">
                    {product.status === "staged" ? (
                      <PromoteSupplierProductDialog
                        storeId={storeId}
                        supplierProductId={product.id}
                        suggestedName={product.name}
                        suggestedPriceAmount={product.suggested_price_amount}
                      />
                    ) : null}
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
