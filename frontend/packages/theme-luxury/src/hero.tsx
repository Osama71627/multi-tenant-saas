/** Vast negative space, centered thin type, a single hairline rule --
 * the "quiet luxury" hero convention: no color block, no background
 * image treatment, nothing bold. Deliberately the visual opposite of
 * Electronics's dense gradient/badge hero. */
export function LuxuryHero({ headline, subheadline }: { headline: string; subheadline: string }) {
  if (!headline && !subheadline) return null;

  return (
    <section className="px-4 py-40 text-center">
      <div className="mx-auto max-w-xl space-y-6">
        {headline ? (
          <h1 className="text-3xl font-light tracking-[0.05em] sm:text-4xl" style={{ color: "var(--sf-primary)" }}>
            {headline}
          </h1>
        ) : null}
        <div className="mx-auto h-px w-12" style={{ backgroundColor: "var(--sf-accent)" }} />
        {subheadline ? (
          <p className="text-sm font-light italic text-gray-500">{subheadline}</p>
        ) : null}
      </div>
    </section>
  );
}
