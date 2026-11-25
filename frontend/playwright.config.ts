import { defineConfig, devices } from "@playwright/test";

/**
 * Testes ponta a ponta (spec 011, FR-179).
 *
 * - No CI: build de produção do Next na porta 3100, com a API simulada pelos dados gravados
 *   em e2e/fixtures/ (nenhuma chamada sai para a internet).
 * - Gravação (E2E_RECORD=1): roda contra a plataforma local já no ar (E2E_BASE_URL) e grava
 *   as respostas reais da API. Veja e2e/README.md.
 */
const record = process.env.E2E_RECORD === "1";
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: !record,
  workers: record ? 1 : undefined,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: record ? 120_000 : 30_000,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: record
    ? undefined
    : {
        command: "npm run build && npx next start --port 3100",
        url: "http://localhost:3100",
        timeout: 300_000,
        reuseExistingServer: !process.env.CI,
        env: { API_INTERNAL_URL: "http://127.0.0.1:9" },
      },
});
