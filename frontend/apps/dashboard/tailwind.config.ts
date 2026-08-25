import preset from "@saas/config/tailwind-preset";
import type { Config } from "tailwindcss";

const config: Config = {
  presets: [preset],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
    "../../packages/theme-aurora/src/**/*.{ts,tsx}",
  ],
};

export default config;
