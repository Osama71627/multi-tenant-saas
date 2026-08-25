import type { CSSProperties } from "react";

import type { AuroraSettings } from "./types";

function fontFamilyVar(choice: string): string {
  switch (choice) {
    case "cairo":
      return "var(--font-cairo)";
    case "tajawal":
      return "var(--font-tajawal)";
    default:
      return "var(--font-inter)";
  }
}

/** Every Aurora color/typography choice becomes a CSS custom property on
 * the page root -- components read `var(--sf-primary)` etc via inline
 * `style`, never a Tailwind class (Tailwind can't statically generate a
 * class for a runtime-dynamic per-store hex value). The consuming app is
 * responsible for actually loading `--font-inter`/`--font-cairo`/
 * `--font-tajawal` via `next/font/google` (font loading has to happen in
 * each app's own build, not this shared package). */
export function auroraCssVars(settings: AuroraSettings): CSSProperties {
  return {
    "--sf-primary": settings.primary_color,
    "--sf-secondary": settings.secondary_color,
    "--sf-accent": settings.accent_color,
    "--font-sans": fontFamilyVar(settings.font_choice),
  } as CSSProperties;
}
