import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirrors tsconfig.json's "@/*" -> "./*" path mapping -- tsc
    // resolves it for type-checking, but Vite/Vitest need their own
    // alias to resolve it at actual module-load time (only surfaces
    // once a test imports a component that itself has an "@/..."
    // import, which no test here did before this one).
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
});
