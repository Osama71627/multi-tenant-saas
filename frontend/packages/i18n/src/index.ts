/**
 * Shared i18n config -- docs/ARCHITECTURE.md: "next-intl (ar/en)", "دعم
 * عربي/إنجليزي كامل من اليوم الأول". `dir` is derived from `locale`
 * here, never stored/guessed separately -- Arabic is always RTL, English
 * always LTR, so there is exactly one source of truth per locale, not
 * two independently-settable values that could drift apart.
 */
export const locales = ["en", "ar"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

export function directionForLocale(locale: Locale): "ltr" | "rtl" {
  return locale === "ar" ? "rtl" : "ltr";
}
