import type { CSSProperties } from "react";

import type { FashionSettings } from "./types";

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

/** Same `--sf-*` variable contract as `@saas/theme-aurora`'s
 * `auroraCssVars` -- every theme package reads/writes the identical CSS
 * custom-property names, so the consuming app's layout doesn't need to
 * know which theme is active to apply them. */
export function fashionCssVars(settings: FashionSettings): CSSProperties {
  return {
    "--sf-primary": settings.primary_color,
    "--sf-secondary": settings.secondary_color,
    "--sf-accent": settings.accent_color,
    "--font-sans": fontFamilyVar(settings.font_choice),
  } as CSSProperties;
}
