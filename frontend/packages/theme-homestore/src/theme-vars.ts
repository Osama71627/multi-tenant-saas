import type { CSSProperties } from "react";

import type { HomestoreSettings } from "./types";

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

/** Same `--sf-*` variable contract as every other theme's `xCssVars` --
 * see @saas/theme-fashion/src/theme-vars.ts's own note. */
export function homestoreCssVars(settings: HomestoreSettings): CSSProperties {
  return {
    "--sf-primary": settings.primary_color,
    "--sf-secondary": settings.secondary_color,
    "--sf-accent": settings.accent_color,
    "--font-sans": fontFamilyVar(settings.font_choice),
  } as CSSProperties;
}
