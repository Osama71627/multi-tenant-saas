import { getTranslations } from "next-intl/server";

import { serverFetch } from "@/lib/session";

export const dynamic = "force-dynamic";

interface AuditLogEntry {
  id: string;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: string;
  store_id: string | null;
  created_at: string;
}

async function getAuditLogs(): Promise<AuditLogEntry[]> {
  const response = await serverFetch("api/v1/platform/audit-logs");
  if (!response.ok) return [];
  return response.json();
}

export default async function AuditLogsPage() {
  const t = await getTranslations("platformAdmin.auditLogs");
  const logs = await getAuditLogs();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("title")}</h1>

      {logs.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{t("when")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("actor")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("action")}</th>
                <th className="px-4 py-2 text-start font-medium">{t("target")}</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b last:border-0">
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">{log.actor_email}</td>
                  <td className="px-4 py-2 font-mono text-xs">{log.action}</td>
                  <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                    {log.target_type}:{log.target_id}
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
