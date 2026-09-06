import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    // Los specs de Playwright (e2e/) usan @playwright/test, no vitest.
    exclude: [...configDefaults.exclude, "e2e/**", "playwright.config.ts"],
  },
});
