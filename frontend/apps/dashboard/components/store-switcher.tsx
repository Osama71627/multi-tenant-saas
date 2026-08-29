"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@saas/ui/dropdown-menu";
import { Skeleton } from "@saas/ui/skeleton";
import { Check, ChevronsUpDown, Plus, Store as StoreIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { useStores } from "@/lib/hooks/use-stores";

/**
 * The store switcher (docs/ARCHITECTURE.md section 7.3: "محدّد المتجر
 * (store switcher) في الـ layout"). Every entry links to
 * `/stores/[storeId]/...` -- switching stores is a real navigation, not
 * client-only state, matching how the dashboard route structure mirrors
 * the API path-based tenant resolution 1:1.
 */
export function StoreSwitcher({ locale, currentStoreId }: { locale: string; currentStoreId: string }) {
  const t = useTranslations("storeSwitcher");
  const { data: stores, isLoading } = useStores();
  const currentStore = stores?.find((s) => s.id === currentStoreId);

  if (isLoading) return <Skeleton className="h-9 w-40" />;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-9 min-w-40 items-center gap-2 rounded-md border px-3 text-sm font-medium hover:bg-accent">
        <StoreLogo logo={currentStore?.logo} />
        <span className="truncate">{currentStore?.name ?? t("label")}</span>
        <ChevronsUpDown className="ms-auto h-4 w-4 shrink-0 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>{t("label")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {stores?.length ? (
          stores.map((store) => (
            <DropdownMenuItem key={store.id} asChild>
              <Link href={`/${locale}/stores/${store.id}`} className="flex items-center gap-2">
                <StoreLogo logo={store.logo} />
                <span className="flex-1 truncate">{store.name}</span>
                {store.id === currentStoreId ? <Check className="h-4 w-4" /> : null}
              </Link>
            </DropdownMenuItem>
          ))
        ) : (
          <div className="px-2 py-1.5 text-sm text-muted-foreground">{t("noStores")}</div>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          {/* "/onboarding" used to create a free Store with no plan/payment
              -- points at "/plans" now (see app/page.tsx's docstring) so
              an existing merchant adding another store goes through the
              same payment-gated flow as a first-time one. */}
          <Link href={`/${locale}/plans`} className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            {t("createStore")}
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Real gap found live: `Store.logo` (Phase F's business-info upload)
 * saved to disk and to the DB correctly, but nothing anywhere ever
 * rendered it back -- a merchant had no way to confirm their upload
 * actually became their store's logo. The switcher (present in every
 * dashboard page's header) is the highest-visibility place to close
 * that gap. Falls back to the same generic `StoreIcon` as before when
 * a store has no logo set (the normal case for most stores, and the
 * only case before this fix existed at all).
 */
function StoreLogo({ logo }: { logo?: string | null }) {
  if (!logo) {
    return <StoreIcon className="h-4 w-4 shrink-0 text-muted-foreground" />;
  }
  return (
    // A real, absolute, cross-origin URL (Django's own media host, see
    // apps.stores.serializers.StoreListItemSerializer.get_logo) --
    // next/image's optimizer only handles configured origins/local
    // assets, not an arbitrary per-tenant one.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={logo} alt="" className="h-4 w-4 shrink-0 rounded-sm object-cover" />
  );
}
