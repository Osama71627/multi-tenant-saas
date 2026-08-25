import { getTranslations } from "next-intl/server";

// Deliberately static/decorative -- no email capture form. There is no
// mailing-list backend anywhere in this platform, and a form that looks
// like it submits but goes nowhere would be a fake affordance.
export async function AuroraNewsletter() {
  const t = await getTranslations("storefront.home");

  return (
    <section className="border-t bg-gray-50 px-4 py-14 text-center">
      <div className="mx-auto max-w-md space-y-2">
        <h2 className="text-xl font-semibold">{t("newsletterTitle")}</h2>
        <p className="text-sm text-gray-600">{t("newsletterBody")}</p>
      </div>
    </section>
  );
}
