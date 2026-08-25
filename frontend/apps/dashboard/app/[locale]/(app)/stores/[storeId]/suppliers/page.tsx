import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { CreateSupplierDialog } from "@/components/create-supplier-dialog";
import { SyncSupplierButton } from "@/components/sync-supplier-button";
import { serverFetch } from "@/lib/session";

interface Supplier {
  id: string;
  name: string;
  provider_key: string;
  is_active: boolean;
  pricing_strategy: string;
  pricing_value: number;
  last_synced_at: string | null;
}

async function getSuppliers(storeId: string): Promise<Supplier[]> {
  const response = await serverFetch(`api/v1/dashboard/stores/${storeId}/suppliers`);
  if (!response.ok) return [];
  return response.json();
}

export default async function SuppliersPage({
  params,
}: {
  params: Promise<{ locale: string; storeId: string }>;
}) {
  const { locale, storeId } = await params;
  const t = await getTranslations("suppliers");
  const suppliers = await getSuppliers(storeId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <CreateSupplierDialog storeId={storeId} />
      </div>

      {suppliers.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("name")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("pricingStrategy")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("lastSynced")}</th>
                <th className="px-4 py-2" />
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {suppliers.map((supplier) => (
                <tr key={supplier.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">
                    <Link
                      href={`/${locale}/stores/${storeId}/suppliers/${supplier.id}`}
                      className="hover:underline"
                    >
                      {supplier.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant="secondary">
                      {supplier.pricing_strategy} · {supplier.pricing_value}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {supplier.last_synced_at
                      ? new Date(supplier.last_synced_at).toLocaleString()
                      : t("never")}
                  </td>
                  <td className="px-4 py-2">
                    <SyncSupplierButton storeId={storeId} supplierId={supplier.id} />
                  </td>
                  <td className="px-4 py-2 text-end">
                    <Link
                      href={`/${locale}/stores/${storeId}/suppliers/${supplier.id}`}
                      className="text-sm text-primary hover:underline"
                    >
                      {t("viewProducts")}
                    </Link>
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
