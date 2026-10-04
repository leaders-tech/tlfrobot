import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8766", headless: true },
  webServer: { command: "node demo/serve.mjs 8766", url: "http://127.0.0.1:8766/", reuseExistingServer: true },
});
