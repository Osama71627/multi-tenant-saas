"use client";

import { cn } from "@saas/ui/lib/cn";
import {
  ClipboardList,
  CreditCard,
  LayoutGrid,
  Store as StoreIcon,
  Users as UsersIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { UserMenu } from "@/components/user-menu";

const NAV_ITEMS = [
  { key: "overview", href: "", icon: LayoutGrid },
  { key: "stores", href: "/stores", icon: StoreIcon },
  { key: "plans", href: "/plans", icon: CreditCard },
  { key: "subscriptions", href: "/subscriptions", icon: CreditCard },
  { key: "users", href: "/users", icon: UsersIcon },
  { key: "auditLogs", href: "/audit-logs", icon: ClipboardList },
] as const;

export function AdminShell({
  locale,
  userEmail,
  children,
}: {
  locale: string;
  userEmail: string;
  children: ReactNode;
}) {
  const tNav = useTranslations("platformAdmin.nav");
  const tBrand = useTranslations("platformAdmin");
  const pathname = usePathname();
  const base = `/${locale}`;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-e bg-muted/20 md:flex md:flex-col">
        <div className="flex h-14 items-center border-b px-4 font-semibold">{tBrand("brand")}</div>
        <nav className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map((item) => {
            const href = `${base}${item.href}`;
            const active = item.href === "" ? pathname === base : pathname.startsWith(href);
            const Icon = item.icon;
            return (
              <Link
                key={item.key}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {tNav(item.key)}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-4 border-b px-4">
          <UserMenu locale={locale} email={userEmail} />
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
