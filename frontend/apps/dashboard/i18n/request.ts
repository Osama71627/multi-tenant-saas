import { defaultLocale, isLocale, type Locale } from "@saas/i18n";
import type { AbstractIntlMessages } from "next-intl";
import { getRequestConfig } from "next-intl/server";

// @saas/i18n ships the message catalogs so every app (dashboard,
// storefront, platform-admin) shares one translation source instead of
// three independently-drifting copies. A static per-locale import map
// (not a dynamic `import(`.../${locale}.json`)` template) -- Node's
// package `exports` field only resolves EXACT subpaths it lists, and a
// runtime-computed template literal defeats both that and webpack's
// static-import analysis (confirmed while building this: the dynamic
// form failed to resolve at all).
const MESSAGE_LOADERS: Record<Locale, () => Promise<{ default: AbstractIntlMessages }>> = {
  en: () => import("@saas/i18n/messages/en"),
  ar: () => import("@saas/i18n/messages/ar"),
};

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = requested && isLocale(requested) ? requested : defaultLocale;

  return {
    locale,
    messages: (await MESSAGE_LOADERS[locale]()).default,
  };
});
