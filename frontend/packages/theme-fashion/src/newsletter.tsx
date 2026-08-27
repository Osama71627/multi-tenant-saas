import { getTranslations } from "next-intl/server";

// Deliberately static/decorative -- see Aurora's identical note: no
// mailing-list backend exists anywhere in this platform.
export async function FashionNewsletter() {
  const t = await getTranslations("storefront.home");

  return (
    <section className="px-4 py-20 text-center text-white" style={{ backgroundColor: "var(--sf-primary)" }}>
      <div className="mx-auto max-w-md space-y-3">
        <h2 className="font-serif text-2xl">{t("newsletterTitle")}</h2>
        <p className="text-sm font-light text-white/75">{t("newsletterBody")}</p>
      </div>
    </section>
  );
}
