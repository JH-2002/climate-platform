import { expect, RECORD, test } from "./api";

async function settle(page: import("@playwright/test").Page) {
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
}

test("página de alertas", async ({ page }) => {
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { level: 1, name: "Alertas" })).toBeVisible();
  await settle(page);
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  await expect(page.getByText(/Defesa Civil/).first()).toBeVisible();
});

test("risco com filtro e detalhe do setor", async ({ page }) => {
  await page.goto("/risk");
  await expect(page.getByRole("heading", { level: 1, name: "Risco de alagamento estimado" })).toBeVisible();
  const sectors = page.getByRole("button", { name: /^Ver explicação do setor/ });
  await expect(sectors.first()).toBeVisible({ timeout: 15_000 });

  await page.getByLabel("Categoria").selectOption({ index: 1 });
  await expect(page).toHaveURL(/categoria=/);
  await settle(page);

  await page.getByLabel("Categoria").selectOption("");
  await expect(page).not.toHaveURL(/categoria=/);
  await expect(sectors.first()).toBeVisible();
  const name = (await sectors.first().getAttribute("aria-label"))!.replace("Ver explicação do setor ", "");
  await sectors.first().click();
  await expect(page).toHaveURL(/setor=/);
  await expect(page.getByRole("heading", { level: 2, name: new RegExp(`^Setor ${name}`) })).toBeVisible();
  await settle(page);
});

test("relatórios: pedido, andamento e download", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Relatórios" })).toBeVisible();
  await settle(page);
  await page.getByRole("button", { name: "Gerar relatório" }).click();

  const download = page.getByRole("link", { name: /^Baixar / });
  await expect(download.first()).toBeVisible({ timeout: RECORD ? 90_000 : 15_000 });
  const [file] = await Promise.all([page.waitForEvent("download"), download.first().click()]);
  expect(file.suggestedFilename()).toMatch(/\.(pdf|csv|json)$/);
  await settle(page);
});

test("laboratório com cenário pronto", async ({ page }) => {
  await page.goto("/simulation");
  await expect(page.getByRole("heading", { level: 1, name: "Laboratório de simulação" })).toBeVisible();
  const presets = page.getByRole("group", { name: "Cenários prontos" }).getByRole("button");
  await expect(presets.first()).toBeVisible({ timeout: 15_000 });
  await presets.first().click();
  await expect(presets.first()).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Simular" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Resultado da simulação" })).toBeVisible({
    timeout: RECORD ? 90_000 : 15_000,
  });
  await settle(page);
});
