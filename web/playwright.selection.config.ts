import { defineConfig } from "@playwright/test";
import liveConfig from "./playwright.config";

export default defineConfig({
  ...liveConfig,
  use: { ...liveConfig.use, baseURL: "http://localhost:3100" },
  testDir: "./selection-tests",
  testMatch: "report-selection.spec.ts",
  webServer: [
    {
      command: `"${process.env.FOLIO_TEST_PYTHON ?? "../backend/.venv/bin/python"}" selection-tests/selection-backend.py`,
      url: "http://127.0.0.1:8011/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run start -- --hostname 127.0.0.1 --port 3100",
      url: "http://localhost:3100",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
