export function AuroraFooter({ storeName }: { storeName: string }) {
  return (
    <footer className="border-t bg-white">
      <div className="mx-auto max-w-6xl px-4 py-8 text-center text-sm text-gray-500">
        © {new Date().getFullYear()} {storeName}
      </div>
    </footer>
  );
}
