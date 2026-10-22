import { defineConfig } from "@playwright/test";
import config from "./playwright.config";

export default defineConfig({
  ...config,
  testMatch: "report-selection.spec.ts",
  reporter: "list",
  use: { ...config.use, baseURL: "http://localhost:3100" },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3100",
    url: "http://localhost:3100",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
