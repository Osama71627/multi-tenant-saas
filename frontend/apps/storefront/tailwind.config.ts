import preset from "@saas/config/tailwind-preset";
import type { Config } from "tailwindcss";

// Real bug found live -- see apps/dashboard/tailwind.config.ts's
// identical comment: this app renders every theme package
// (components/theme-registry.tsx) for a real shopper on any tenant's
// real storefront, but Tailwind only ever scanned theme-aurora's
// source. Any utility class used ONLY inside one of the other theme
// packages was silently purged from this app's OWN compiled CSS too.
// Every new theme package MUST be added here (and to
// apps/dashboard/tailwind.config.ts) the moment it's registered in
// theme-registry.tsx.
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
