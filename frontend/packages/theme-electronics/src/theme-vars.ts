import type { CSSProperties } from "react";

import type { ElectronicsSettings } from "./types";

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

export function electronicsCssVars(settings: ElectronicsSettings): CSSProperties {
  return {
    "--sf-primary": settings.primary_color,
    "--sf-secondary": settings.secondary_color,
    "--sf-accent": settings.accent_color,
    "--font-sans": fontFamilyVar(settings.font_choice),
  } as CSSProperties;
}
