import type { ReactNode } from "react";

// Locale/dir are set in app/[locale]/layout.tsx -- see
// apps/dashboard/app/layout.tsx for why this root layout stays empty.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
