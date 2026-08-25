import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// CSP itself is set per-request in middleware.ts (needs a fresh nonce
// every time) -- these are the remaining, request-independent headers
// from docs/ARCHITECTURE.md section 12's Headers row.
const STATIC_SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@saas/ui", "@saas/auth", "@saas/i18n", "@saas/api-client"],
  eslint: {
    dirs: ["app", "lib", "components"],
  },
  async headers() {
    return [{ source: "/(.*)", headers: STATIC_SECURITY_HEADERS }];
  },
};

export default withNextIntl(nextConfig);
