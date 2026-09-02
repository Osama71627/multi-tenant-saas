import preset from "@saas/config/tailwind-preset";
import type { Config } from "tailwindcss";

// Real bug found live: this app's own live-preview renders every theme
// package (components/preview/theme-registry.tsx), but Tailwind only
// ever scanned theme-aurora's source for class names -- any utility
// class used ONLY inside one of the other theme packages (never
// elsewhere in this app, @saas/ui, or theme-aurora) was silently
// PURGED from the compiled CSS in a real production build. Invisible in
// `next dev` (which doesn't purge as aggressively) and invisible to
// typecheck/lint -- only found by inspecting a real `next start`
// build's actual computed styles (a Fashion-only class, `gap-x-8` on
// FashionFooter's nav row, had `gap: normal` instead of 2rem: the
// class was never in any stylesheet at all). Every new theme package
// MUST be added here (and to apps/storefront/tailwind.config.ts) the
// moment it's registered in theme-registry.tsx -- easy to forget again.
const config: Config = {
  presets: [preset],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
    "../../packages/theme-aurora/src/**/*.{ts,tsx}",
    "../../packages/theme-electronics/src/**/*.{ts,tsx}",
    "../../packages/theme-fashion/src/**/*.{ts,tsx}",
    "../../packages/theme-luxury/src/**/*.{ts,tsx}",
    "../../packages/theme-homestore/src/**/*.{ts,tsx}",
  ],
};

export default config;
