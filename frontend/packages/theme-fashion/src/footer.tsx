/** Dark, editorial footer -- the large wordmark + small print
 * convention, structurally different from Aurora's single-line
 * light-background footer. */
export function FashionFooter({ storeName }: { storeName: string }) {
  return (
    <footer className="px-4 py-14 text-center text-white" style={{ backgroundColor: "var(--sf-primary)" }}>
      <p className="font-serif text-2xl tracking-wide">{storeName}</p>
      <p className="mt-3 text-xs uppercase tracking-[0.3em] text-white/50">
        © {new Date().getFullYear()}
      </p>
    </footer>
  );
}
