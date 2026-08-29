import { ArrowRight } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

// A faint diagonal crosshatch over the solid colour block -- the same
// "texture without a loud gradient" trick used elsewhere in this
// project's own design language (see apps/dashboard's theme-marketplace
// page), kept at low opacity so it reads as texture, not a pattern.
const HERO_PATTERN =
  "url(\"data:image/svg+xml,%3Csvg width='28' height='28' viewBox='0 0 28 28' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0l28 28M28 0L0 28' stroke='%23FFFFFF' stroke-opacity='0.06' stroke-width='1'/%3E%3C/svg%3E\")";

/**
 * Full-bleed editorial hero: a solid colour block (no photography
 * asset pipeline exists in this project), tall vertical rhythm, serif
 * display headline, small tracked "eyebrow" label, a real CTA into the
 * catalog, and a faint diagonal texture so the block reads as a
 * considered design choice rather than a flat placeholder -- the
 * fashion-catalog convention, structurally different from Aurora's
 * compact centered banner (taller, different type treatment, an
 * eyebrow row + CTA Aurora doesn't have at all).
 */
export async function FashionHero({
  headline,
  subheadline,
  shopHref,
}: {
  headline: string;
  subheadline: string;
  /** Where the CTA points -- the real storefront passes its own
   * `/${locale}/products`; the dashboard's live-preview host has no
   * real catalog route, so it passes a non-navigating anchor instead
   * (same "no dead affordance, but no fake route either" posture
   * FashionHeader's own `disableNav` already established). */
  shopHref?: string;
}) {
  if (!headline && !subheadline) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section
      className="relative overflow-hidden px-4 py-28 text-center text-white sm:py-36"
      style={{ backgroundColor: "var(--sf-primary)" }}
    >
      <div className="pointer-events-none absolute inset-0" style={{ backgroundImage: HERO_PATTERN }} />
      <div className="relative mx-auto max-w-2xl space-y-7">
        <p className="text-xs font-medium uppercase tracking-[0.35em] text-white/70">
          {t("newCollection")}
        </p>
        {headline ? (
          <h1 className="font-serif text-5xl leading-[1.1] tracking-tight sm:text-6xl">
            {headline}
          </h1>
        ) : null}
        {subheadline ? (
          <p className="mx-auto max-w-md text-base font-light text-white/80">{subheadline}</p>
        ) : null}
        {shopHref ? (
          <div className="pt-2">
            <Link
              href={shopHref}
              className="inline-flex items-center gap-2 border border-white/40 px-8 py-3 text-xs font-medium uppercase tracking-[0.25em] text-white transition-colors hover:border-white hover:bg-white hover:text-black"
            >
              {t("shopNow")}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        ) : null}
      </div>
    </section>
  );
}
