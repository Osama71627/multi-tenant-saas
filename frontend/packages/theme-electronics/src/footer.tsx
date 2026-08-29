/** Dark footer, bold uppercase wordmark -- consistent with the rest of
 * this theme's dark "tech retailer" surfaces. */
export function ElectronicsFooter({
  storeName,
  logoUrl,
}: {
  storeName: string;
  /** See ElectronicsHeader's identical prop/comment -- same light
   * backing chip, needed for the same reason on this dark footer. */
  logoUrl?: string | null;
  /** Not yet rendered by this theme's footer -- see @saas/theme-aurora's
   * AuroraFooter for why this is declared anyway. */
  navOrder?: Array<"shop" | "about" | "contact">;
  locale?: string;
  disableNav?: boolean;
}) {
  return (
    <footer
      className="border-t border-white/10 px-4 py-8 text-center"
      style={{ backgroundColor: "var(--sf-primary)" }}
    >
      {logoUrl ? (
        <span className="mb-2 inline-block rounded-md bg-white/95 px-2 py-1">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={logoUrl} alt={storeName} className="h-5 w-auto object-contain" />
        </span>
      ) : null}
      <p className="text-sm font-bold uppercase tracking-wide text-white">{storeName}</p>
      <p className="mt-1 text-xs text-white/50">© {new Date().getFullYear()}</p>
    </footer>
  );
}
