import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";

import { StoreActions } from "@/components/store-actions";
import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface PlatformStore {
  id: string;
  name: string;
  slug: string;
  status: string;
  default_currency: string;
  contact_email: string;
  contact_phone: string;
  created_at: string;
}

async function getStores(): Promise<PlatformStore[]> {
  const response = await serverFetch("api/v1/platform/stores");
  if (!response.ok) return [];
  return response.json();
}

function statusVariant(status: string): "success" | "destructive" | "secondary" {
  if (status === "active") return "success";
  if (status === "suspended") return "destructive";
  return "secondary";
}

export default async function StoresPage() {
  const t = await getTranslations("platformAdmin.stores");
  const stores = await getStores();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("title")}</h1>

      {stores.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-start">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("name")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("slug")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("status")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("currency")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("created")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {stores.map((store) => (
                <tr key={store.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">{store.name}</td>
                  <td className="px-4 py-2 text-muted-foreground">{store.slug}</td>
                  <td className="px-4 py-2">
                    <Badge variant={statusVariant(store.status)}>{store.status}</Badge>
                  </td>
                  <td className="px-4 py-2">{store.default_currency}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(store.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-end">
                    <StoreActions storeId={store.id} status={store.status} />
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
