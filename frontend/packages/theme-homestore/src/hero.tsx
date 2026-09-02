import { ArrowRight } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

/**
 * Rich gradient hero banner -- source design used a real photographic
 * slider (multiple rotating banner images); no per-store hero-image
 * field exists in this project's settings contract yet (a real,
 * separate, not-yet-built feature -- same "no photo" constraint every
 * other theme's own Hero documents), so this uses a bold two-tone
 * gradient + a soft radial glow instead, keeping the same "considered
 * design choice, not a placeholder" posture.
 */
export async function HomestoreHero({
  headline,
  subheadline,
  shopHref,
}: {
  headline: string;
  subheadline: string;
  shopHref?: string;
}) {
  if (!headline && !subheadline) return null;
  const t = await getTranslations("storefront.home");

  return (
    <section
      className="relative flex min-h-[65vh] items-center overflow-hidden text-white"
      style={{
        background: "linear-gradient(135deg, var(--sf-primary), color-mix(in srgb, var(--sf-primary) 60%, black))",
      }}
    >
      <div
        className="pointer-events-none absolute -top-24 right-0 h-96 w-96 rounded-full opacity-20 blur-3xl"
        style={{ backgroundColor: "var(--sf-secondary)" }}
      />
      <div
        className="pointer-events-none absolute -bottom-24 left-0 h-96 w-96 rounded-full opacity-10 blur-3xl"
        style={{ backgroundColor: "var(--sf-accent)" }}
      />
      <div className="relative mx-auto max-w-7xl px-4 py-24 lg:px-8">
        <div className="max-w-xl space-y-6">
          <span className="inline-block rounded-full bg-white/15 px-4 py-1.5 text-sm font-medium backdrop-blur-sm">
            {t("newArrivals")}
          </span>
          {headline ? (
            <h1 className="text-4xl font-bold leading-tight sm:text-5xl lg:text-6xl">{headline}</h1>
          ) : null}
          {subheadline ? (
            <p className="text-lg text-white/80 sm:text-xl">{subheadline}</p>
          ) : null}
          {shopHref ? (
            <Link
              href={shopHref}
              className="inline-flex items-center gap-2 rounded-full bg-white px-8 py-4 font-semibold text-neutral-900 transition-all hover:scale-105 hover:shadow-lg"
            >
              {t("shopNow")}
              <ArrowRight className="h-4 w-4" />
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}
