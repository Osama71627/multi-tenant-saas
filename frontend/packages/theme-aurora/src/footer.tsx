export function AuroraFooter({
  storeName,
  logoUrl,
}: {
  storeName: string;
  /** See AuroraHeader's identical prop for the full "logo was write-only"
   * story -- same fallback-to-text-wordmark behavior here. */
  logoUrl?: string | null;
  /** Not yet rendered by this theme's footer (its own redesign pass
   * hasn't happened yet) -- declared so the shared registry's
   * `<theme.Footer navOrder={...} locale={...} disableNav={...} />`
   * call stays valid across every theme (see @saas/theme-fashion's
   * FashionFooter, which does render a nav row, for the fuller story). */
  navOrder?: Array<"shop" | "about" | "contact">;
  locale?: string;
  disableNav?: boolean;
}) {
  return (
    <footer className="border-t bg-white">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-8 text-center text-sm text-gray-500">
        {logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logoUrl} alt={storeName} className="h-6 w-auto object-contain opacity-80" />
        ) : null}
        <span>
          © {new Date().getFullYear()} {storeName}
        </span>
      </div>
    </footer>
  );
}
