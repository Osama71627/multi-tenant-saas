"use client";

import { cn } from "@saas/ui/lib/cn";
import {
  Boxes,
  CreditCard,
  LayoutGrid,
  Package,
  Receipt,
  Settings,
  ShoppingCart,
  Truck,
  Warehouse,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { StoreSwitcher } from "@/components/store-switcher";
import { UserMenu } from "@/components/user-menu";

const NAV_ITEMS = [
  { key: "overview", href: "", icon: LayoutGrid },
  { key: "products", href: "/products", icon: Package },
  { key: "inventory", href: "/inventory", icon: Warehouse },
  { key: "orders", href: "/orders", icon: ShoppingCart },
  { key: "shipping", href: "/shipping", icon: Truck },
  { key: "payments", href: "/payments", icon: CreditCard },
  { key: "suppliers", href: "/suppliers", icon: Boxes },
  { key: "subscription", href: "/subscription", icon: Receipt },
] as const;

export function DashboardShell({
  locale,
  storeId,
  userEmail,
  children,
}: {
  locale: string;
  storeId: string;
  userEmail: string;
  children: ReactNode;
}) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const base = `/${locale}/stores/${storeId}`;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-e bg-muted/20 md:flex md:flex-col">
        <div className="flex h-14 items-center border-b px-4 font-semibold">Multi-Tenant SaaS</div>
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
                {t(item.key)}
              </Link>
            );
          })}
        </nav>
        <div className="border-t p-3">
          <Link
            href={`${base}/settings`}
            className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            <Settings className="h-4 w-4 shrink-0" />
            {t("settings")}
          </Link>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-4 border-b px-4">
          <StoreSwitcher locale={locale} currentStoreId={storeId} />
          <UserMenu locale={locale} email={userEmail} />
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
