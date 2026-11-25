import { activeAlerts } from "../tests/alertsFixtures";
import { expect, RECORD, test } from "./api";

test("visão geral com a faixa de alerta oficial", async ({ page, api }) => {
  // A faixa depende de haver alerta vigente; o estado é fixado para o teste não depender do dia.
  api.override(/^GET \/api\/v1\/alerts\/active/, activeAlerts());
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Visão geral" })).toBeVisible();
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
  if (RECORD) return;

  const banner = page.getByRole("link", { name: "Ver alerta" });
  await expect(banner).toBeVisible();
  await expect(page.getByText("Alerta oficial — Defesa Civil").first()).toBeVisible();
  await banner.click();
  await expect(page).toHaveURL(/\/alerts/);
});

test("visão geral sem alerta vigente não mostra a faixa", async ({ page, api }) => {
  api.override(
    /^GET \/api\/v1\/alerts\/active/,
    activeAlerts({
      official: [],
      system: [],
      counts: {
        official_active: 0,
        official_upcoming: 0,
        civil_defense_active: 0,
        weather_warning_active: 0,
        risk_estimate: 0,
        data_quality: 0,
      },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Visão geral" })).toBeVisible();
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
  if (RECORD) return;
  await expect(page.getByRole("link", { name: /^Ver alerta/ })).toHaveCount(0);
});
