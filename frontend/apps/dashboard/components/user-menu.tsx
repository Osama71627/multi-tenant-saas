"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@saas/ui/dropdown-menu";
import { LogOut, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

export function UserMenu({ locale, email }: { locale: string; email: string }) {
  const t = useTranslations("userMenu");
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/bff/logout", { method: "POST" });
    router.push(`/${locale}/login`);
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-sm font-medium">
        {email.slice(0, 1).toUpperCase()}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <div className="px-2 py-1.5 text-sm text-muted-foreground">{email}</div>
        <DropdownMenuSeparator />
        <DropdownMenuItem>
          <User className="h-4 w-4" />
          {t("profile")}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
          {t("logout")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
