import { defaultLocale, isLocale, type Locale } from "@saas/i18n";
import type { AbstractIntlMessages } from "next-intl";
import { getRequestConfig } from "next-intl/server";

// Same static per-locale loader map as apps/dashboard/i18n/request.ts --
// see that file's comment for why a dynamic template-literal import
// doesn't work with Node's package `exports` resolution.
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
