import preset from "@saas/config/tailwind-preset";
import type { Config } from "tailwindcss";

// Real bug found live -- see apps/dashboard/tailwind.config.ts's
// identical comment: this app renders ALL FOUR theme packages
// (components/theme-registry.tsx) for a real shopper on any tenant's
// real storefront, but Tailwind only ever scanned theme-aurora's
// source. Any utility class used ONLY inside theme-fashion/-electronics
// /-luxury was silently purged from this app's OWN compiled CSS too.
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
  ],
};

export default config;
