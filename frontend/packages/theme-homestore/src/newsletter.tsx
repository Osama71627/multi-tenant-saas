import { getTranslations } from "next-intl/server";

// Deliberately static/decorative -- see @saas/theme-fashion's
// FashionNewsletter's identical note: no mailing-list backend exists
// anywhere in this platform. The source design had a real working
// subscribe form (Alpine.js fetch to a Django endpoint); no equivalent
// exists here, so this stays a decorative section, not a fake form
// that would silently do nothing on submit.
export async function HomestoreNewsletter() {
  const t = await getTranslations("storefront.home");

  return (
    <section
      className="relative overflow-hidden px-4 py-16 text-center text-white lg:py-24"
      style={{
        background: "linear-gradient(135deg, var(--sf-secondary), color-mix(in srgb, var(--sf-secondary) 60%, black))",
      }}
    >
      <div className="pointer-events-none absolute -top-20 left-10 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 right-10 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
      <div className="relative mx-auto max-w-xl space-y-3">
        <h2 className="text-3xl font-bold sm:text-4xl">{t("newsletterTitle")}</h2>
        <p className="text-white/85">{t("newsletterBody")}</p>
      </div>
    </section>
  );
}
