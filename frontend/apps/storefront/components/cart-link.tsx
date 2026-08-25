"use client";

import { ShoppingBag } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { useCart } from "@/lib/hooks/use-cart";

export function CartLink({ href }: { href: string }) {
  const t = useTranslations("storefront.nav");
  const { data: cart } = useCart();
  const count = cart?.items?.reduce((sum, item) => sum + item.quantity, 0) ?? 0;

  return (
    <Link href={href} className="relative flex items-center gap-1.5 text-sm font-medium">
      <ShoppingBag className="h-5 w-5" />
      <span>{t("cart")}</span>
      {count > 0 ? (
        <span
          className="absolute -end-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold text-white"
          style={{ backgroundColor: "var(--sf-accent)" }}
        >
          {count}
        </span>
      ) : null}
    </Link>
  );
}
