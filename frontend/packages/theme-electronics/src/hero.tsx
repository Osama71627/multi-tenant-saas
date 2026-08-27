/** Dark gradient "deals" hero with a row of static trust badges --
 * the electronics-retail convention (Free shipping / Warranty /
 * Support), structurally unlike Aurora's/Fashion's plain text hero. */
export function ElectronicsHero({
  headline,
  subheadline,
}: {
  headline: string;
  subheadline: string;
}) {
  if (!headline && !subheadline) return null;

  return (
    <section
      className="px-4 py-20 text-center text-white"
      style={{
        background: "linear-gradient(135deg, var(--sf-primary), var(--sf-secondary))",
      }}
    >
      <div className="mx-auto max-w-2xl space-y-4">
        <p
          className="inline-block rounded px-2 py-1 text-xs font-bold uppercase tracking-wide"
          style={{ backgroundColor: "var(--sf-accent)", color: "var(--sf-primary)" }}
        >
          Limited-time offers
        </p>
        {headline ? <h1 className="text-4xl font-black tracking-tight sm:text-5xl">{headline}</h1> : null}
        {subheadline ? <p className="text-base text-white/80">{subheadline}</p> : null}
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 pt-4 text-xs font-medium uppercase tracking-wide text-white/70">
          <span>Free shipping</span>
          <span>2-year warranty</span>
          <span>24/7 support</span>
        </div>
      </div>
    </section>
  );
}
