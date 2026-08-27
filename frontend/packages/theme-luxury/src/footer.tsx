/** Minimal centered footer, thin top border, tracked small caps --
 * matching this theme's restraint everywhere else. */
export function LuxuryFooter({ storeName }: { storeName: string }) {
  return (
    <footer className="border-t border-gray-100 py-10 text-center">
      <p className="text-xs font-light uppercase tracking-[0.3em] text-gray-500">{storeName}</p>
      <p className="mt-2 text-xs font-light text-gray-300">© {new Date().getFullYear()}</p>
    </footer>
  );
}
