import { defineConfig, devices } from "@playwright/test";

/**
 * Gravação da vitrine pública (spec 012, FR-195). Não é teste: roda no workflow demo.yml contra
 * a plataforma no ar (API real e `next start`) e grava as respostas em DEMO_OUT.
 */
export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 15 * 60_000,
  reporter: "list",
  use: {
    baseURL: process.env.DEMO_BASE_URL ?? "http://localhost:3000",
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
