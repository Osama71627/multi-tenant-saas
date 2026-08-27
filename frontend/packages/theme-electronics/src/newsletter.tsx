import { getTranslations } from "next-intl/server";

export async function ElectronicsNewsletter() {
  const t = await getTranslations("storefront.home");

  return (
    <section className="px-4 py-12 text-center" style={{ backgroundColor: "var(--sf-accent)" }}>
      <div className="mx-auto max-w-md space-y-2">
        <h2 className="text-lg font-black uppercase" style={{ color: "var(--sf-primary)" }}>
          {t("newsletterTitle")}
        </h2>
        <p className="text-sm font-medium" style={{ color: "var(--sf-primary)" }}>
          {t("newsletterBody")}
        </p>
      </div>
    </section>
  );
}
