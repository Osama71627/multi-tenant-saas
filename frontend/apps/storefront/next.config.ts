import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@saas/ui", "@saas/i18n", "@saas/api-client", "@saas/theme-aurora"],
  eslint: {
    dirs: ["app", "lib", "components"],
  },
  async headers() {
    // CSP itself is set per-request in middleware.ts (needs a fresh nonce
    // every time) -- these are the remaining, request-independent headers
    // from docs/ARCHITECTURE.md section 12's Headers row.
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
