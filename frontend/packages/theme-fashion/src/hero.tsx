/**
 * Full-bleed editorial hero: a solid colour block (no photography
 * asset pipeline exists in this project), tall vertical rhythm, serif
 * display headline, small tracked "eyebrow" label -- the fashion-
 * catalog convention, structurally different from Aurora's compact
 * centered banner (taller, different type treatment, an eyebrow row
 * Aurora doesn't have at all).
 */
export function FashionHero({
  headline,
  subheadline,
}: {
  headline: string;
  subheadline: string;
}) {
  if (!headline && !subheadline) return null;

  return (
    <section
      className="px-4 py-32 text-center text-white"
      style={{ backgroundColor: "var(--sf-primary)" }}
    >
      <div className="mx-auto max-w-2xl space-y-6">
        <p className="text-xs font-medium uppercase tracking-[0.35em] text-white/70">
          New Collection
        </p>
        {headline ? (
          <h1 className="font-serif text-5xl tracking-tight sm:text-6xl">{headline}</h1>
        ) : null}
        {subheadline ? (
          <p className="text-base font-light text-white/80">{subheadline}</p>
        ) : null}
      </div>
    </section>
  );
}
