/** Dark footer, bold uppercase wordmark -- consistent with the rest of
 * this theme's dark "tech retailer" surfaces. */
export function ElectronicsFooter({ storeName }: { storeName: string }) {
  return (
    <footer className="border-t border-white/10 px-4 py-8 text-center" style={{ backgroundColor: "var(--sf-primary)" }}>
      <p className="text-sm font-bold uppercase tracking-wide text-white">{storeName}</p>
      <p className="mt-1 text-xs text-white/50">© {new Date().getFullYear()}</p>
    </footer>
  );
}
