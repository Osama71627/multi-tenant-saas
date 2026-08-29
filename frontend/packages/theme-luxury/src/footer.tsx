/** Minimal centered footer, thin top border, tracked small caps --
 * matching this theme's restraint everywhere else. */
export function LuxuryFooter({
  storeName,
  logoUrl,
}: {
  storeName: string;
  /** See LuxuryHeader's identical prop for the full "logo was write-only"
   * story -- same fallback-to-text-wordmark behavior here. */
  logoUrl?: string | null;
  /** Not yet rendered by this theme's footer -- see @saas/theme-aurora's
   * AuroraFooter for why this is declared anyway. */
  navOrder?: Array<"shop" | "about" | "contact">;
  locale?: string;
  disableNav?: boolean;
}) {
  return (
    <footer className="border-t border-gray-100 py-10 text-center">
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt={storeName}
          className="mx-auto mb-3 h-6 w-auto object-contain opacity-70"
        />
      ) : null}
      <p className="text-xs font-light uppercase tracking-[0.3em] text-gray-500">{storeName}</p>
      <p className="mt-2 text-xs font-light text-gray-300">© {new Date().getFullYear()}</p>
    </footer>
  );
}
