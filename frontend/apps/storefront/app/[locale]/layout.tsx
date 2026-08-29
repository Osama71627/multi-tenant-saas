import "@saas/ui/globals.css";
import { directionForLocale, locales, type Locale } from "@saas/i18n";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { CartLink } from "@/components/cart-link";
import { QueryProvider } from "@/components/query-provider";
import { getCssVars, getTheme } from "@/components/theme-registry";
import { FONT_VARIABLES } from "@/lib/fonts";
import { getStorefrontContext } from "@/lib/theme";

// No `generateStaticParams` here on purpose (unlike apps/dashboard's
// identical-looking layout) -- every page under this layout is
// genuinely per-tenant (Host-resolved, via `getStorefrontContext()`
// below), never just per-locale, so there is no meaningful "static
// shell" to prebuild. `force-dynamic` makes that explicit rather than
// relying on `headers()` usage alone to opt the route out of static
// optimization.
export const dynamic = "force-dynamic";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!locales.includes(locale as Locale)) notFound();

  const context = await getStorefrontContext();
  if (!context) notFound(); // Unknown hostname -- no Store resolved (same 404 Django itself gives).

  const messages = await getMessages();
  const dir = directionForLocale(locale as Locale);
  const theme = getTheme(context.theme.theme_code);
  const settings = context.theme.settings;

  return (
    <html lang={locale} dir={dir} suppressHydrationWarning className={FONT_VARIABLES}>
      <body
        className="min-h-screen bg-white font-sans antialiased"
        style={{ ...getCssVars(context.theme.theme_code, settings), fontFamily: "var(--font-sans)" }}
      >
        <NextIntlClientProvider messages={messages}>
          <QueryProvider>
            <theme.Header
              storeName={context.store.name}
              logoUrl={context.store.logo}
              navOrder={settings.nav_order}
              locale={locale}
              cartSlot={<CartLink href={`/${locale}/cart`} />}
            />
            <main>{children}</main>
            <theme.Footer
              storeName={context.store.name}
              logoUrl={context.store.logo}
              navOrder={settings.nav_order}
              locale={locale}
            />
          </QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
