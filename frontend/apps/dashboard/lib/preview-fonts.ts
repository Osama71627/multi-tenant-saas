import { Cairo, Inter, Tajawal } from "next/font/google";

// Scoped to the store-preview route only (apps/dashboard/app/[locale]/(app)/stores/[storeId]/preview) --
// mirrors apps/storefront/lib/fonts.ts exactly, since the preview must
// render with the SAME font choices a real shopper would see.
export const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
export const cairo = Cairo({ subsets: ["arabic", "latin"], variable: "--font-cairo" });
export const tajawal = Tajawal({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "700"],
  variable: "--font-tajawal",
});

export const PREVIEW_FONT_VARIABLES = `${inter.variable} ${cairo.variable} ${tajawal.variable}`;
