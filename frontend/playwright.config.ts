import { defineConfig } from "@playwright/test";

/** PostgreSQL descartable para E2E (contenedor postgres-test, puerto 5434). */
const TEST_DB_URL =
  "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://localhost:5199",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      // Backend FastAPI en 8011 apuntando a la DB de test (5434).
      // (8011 y no 8001: el 8001 de este host lo ocupa un contenedor ajeno.)
      // cwd ".." (relativo a frontend/) = raíz del repo, donde vive backend/.
      command: "./.venv/bin/python -m uvicorn backend.app.main:app --port 8011",
      cwd: "..",
      env: {
        ...process.env,
        DATABASE_URL: TEST_DB_URL,
        APP_ENV: "test",
      },
      url: "http://localhost:8011/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Frontend Vite en 5199 apuntando al backend de test.
      command: "npm run dev -- --port 5199 --strictPort",
      env: {
        ...process.env,
        VITE_API_URL: "http://localhost:8011",
      },
      url: "http://localhost:5199",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
