import type { Config } from "tailwindcss";

/**
 * Shared design-system preset (docs/ARCHITECTURE.md: "Tailwind CSS +
 * shadcn/ui + دعم RTL"). RTL support needs no plugin -- Tailwind's core
 * `rtl:`/`ltr:` variants (since v3.3) key off the nearest ancestor's
 * `dir` attribute, which `packages/i18n` sets on `<html dir="rtl|ltr">`.
 * Prefer logical Tailwind utilities (`ms-*`/`me-*`/`ps-*`/`pe-*`,
 * `text-start`/`text-end`) over physical ones (`ml-*`/`text-left`) in
 * app code wherever direction-awareness matters -- those flip
 * automatically with `dir`, no `rtl:` prefix needed at all.
 *
 * shadcn/ui's CSS-variable theme convention (`--background`,
 * `--foreground`, etc.) is intentionally kept: it's what shadcn/ui's own
 * generator (`npx shadcn add <component>`) expects to find already
 * defined, so components can be added to `packages/ui` later without a
 * second, incompatible theme system.
 */
const preset: Config = {
  darkMode: "class",
  content: [],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default preset;
