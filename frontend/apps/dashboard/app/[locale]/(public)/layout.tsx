import type { ReactNode } from "react";

/**
 * The public surface added in Phase A of the "product vision reset":
 * landing page, and (from Phase B on) the theme marketplace/preview --
 * reachable by an anonymous visitor, no auth check at all. Contrast
 * with (app)/layout.tsx, which redirects to /login on every render;
 * this layout intentionally does nothing but pass children through.
 */
export default function PublicLayout({ children }: { children: ReactNode }) {
  return children;
}
