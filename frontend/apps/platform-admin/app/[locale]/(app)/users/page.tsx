import { Badge } from "@saas/ui/badge";
import { getTranslations } from "next-intl/server";

import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface PlatformUserRow {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_platform_staff: boolean;
  created_at: string;
}

async function getUsers(): Promise<PlatformUserRow[]> {
  const response = await serverFetch("api/v1/platform/users");
  if (!response.ok) return [];
  return response.json();
}

export default async function UsersPage() {
  const t = await getTranslations("platformAdmin.users");
  const users = await getUsers();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("title")}</h1>

      {users.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("email")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("fullName")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("active")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("platformStaff")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("joined")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">{user.email}</td>
                  <td className="px-4 py-2">{user.full_name || "—"}</td>
                  <td className="px-4 py-2">
                    <Badge variant={user.is_active ? "success" : "secondary"}>
                      {user.is_active ? "✓" : "—"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">
                    {user.is_platform_staff ? <Badge variant="default">✓</Badge> : null}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString()}
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
