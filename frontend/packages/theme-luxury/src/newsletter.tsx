import { getTranslations } from "next-intl/server";

export async function LuxuryNewsletter() {
  const t = await getTranslations("storefront.home");

  return (
    <section className="border-t border-gray-100 px-4 py-20 text-center">
      <div className="mx-auto max-w-sm space-y-3">
        <h2 className="text-xs font-light uppercase tracking-[0.3em] text-gray-500">
          {t("newsletterTitle")}
        </h2>
        <p className="text-sm font-light text-gray-400">{t("newsletterBody")}</p>
      </div>
    </section>
  );
}
