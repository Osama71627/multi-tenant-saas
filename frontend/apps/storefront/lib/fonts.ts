import { Cairo, Inter, Tajawal } from "next/font/google";

// All three of Aurora's allowed font choices (apps/themes/schemas.py's
// `_ALLOWED_FONTS`) load once at build time via next/font (self-hosted,
// no runtime Google Fonts request) -- which ONE actually applies per
// store is just a CSS variable switch in app/[locale]/layout.tsx, based
// on that store's StoreThemeConfig.settings.font_choice.
export const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
export const cairo = Cairo({ subsets: ["arabic", "latin"], variable: "--font-cairo" });
export const tajawal = Tajawal({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "700"],
  variable: "--font-tajawal",
});

export const FONT_VARIABLES = `${inter.variable} ${cairo.variable} ${tajawal.variable}`;

export function fontFamilyVar(choice: string): string {
  switch (choice) {
    case "cairo":
      return "var(--font-cairo)";
    case "tajawal":
      return "var(--font-tajawal)";
    default:
      return "var(--font-inter)";
  }
}
