import type { ReactNode } from "react";

// Locale/dir are set in app/[locale]/layout.tsx on the actual <html>
// element -- this root layout only exists because Next.js requires
// exactly one, and next-intl's routing always redirects "/" into a
// "/[locale]/..." path (middleware.ts) before this ever renders content
// without a locale segment.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
