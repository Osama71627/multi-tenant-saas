import { Cairo, Playfair_Display } from "next/font/google";

// Scoped to the public theme marketplace only (app/[locale]/(public)/
// themes) -- an editorial display face for the page's own H1, distinct
// from the rest of the dashboard's plain sans UI chrome (globals.css
// sets no display font at all -- see @saas/ui/src/globals.css). Applied
// via `.className` directly on the heading (next/font's simplest form --
// no CSS variable indirection needed since only one element uses it),
// unlike lib/preview-fonts.ts's `.variable` approach, which exists there
// because several elements across a whole iframe need the SAME fonts.
// Playfair Display has no Arabic glyphs, so `ar` gets a bold Cairo
// treatment instead of silently degrading to a generic system serif for
// half of this page's own audience.
export const playfairDisplay = Playfair_Display({ subsets: ["latin"], weight: ["700", "800"] });

export const cairoDisplay = Cairo({ subsets: ["arabic", "latin"], weight: ["700", "800"] });
