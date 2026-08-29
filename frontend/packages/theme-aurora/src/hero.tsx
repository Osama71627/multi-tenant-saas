export function AuroraHero({
  headline,
  subheadline,
}: {
  headline: string;
  subheadline: string;
  /** Not yet used by this theme's hero (its own redesign pass hasn't
   * happened yet) -- declared so the shared registry's `<theme.Hero
   * shopHref={...} />` call stays valid across every theme (see
   * @saas/theme-fashion's FashionHero, which does use it, for the
   * fuller story). */
  shopHref?: string;
}) {
  if (!headline && !subheadline) return null;

  return (
    <section
      className="px-4 py-20 text-center text-white"
      style={{ backgroundColor: "var(--sf-primary)" }}
    >
      <div className="mx-auto max-w-2xl space-y-4">
        {headline ? <h1 className="text-4xl font-bold tracking-tight">{headline}</h1> : null}
        {subheadline ? <p className="text-lg text-white/85">{subheadline}</p> : null}
      </div>
    </section>
  );
}
