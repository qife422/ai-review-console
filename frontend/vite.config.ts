import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => ({
  envDir: mode === "public-demo" ? false : undefined,
  plugins: [react()],
  build: {
    license: { fileName: "licenses/THIRD_PARTY_LICENSES.md" },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
}));
