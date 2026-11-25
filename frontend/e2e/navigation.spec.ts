import { NAV_ITEMS } from "../features/navigation/registry";
import { expect, seriousViolations, test } from "./api";

/** Espera a página assentar: as consultas da API terminam (ou o tempo acaba, com o mapa). */
async function settle(page: import("@playwright/test").Page) {
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
}

test.describe("Navegação por teclado", () => {
  test("link pular para o conteúdo e menu", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Pular para o conteúdo" });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#conteudo$/);

    const menu = page.getByRole("navigation", { name: "Navegação principal" });
    const alerts = menu.getByRole("link", { name: /^Alertas/ });
    await alerts.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/alerts$/);
    await expect(page.getByRole("heading", { level: 1, name: "Alertas" })).toBeVisible();
    await settle(page);
  });
});

test.describe("Acessibilidade (axe) nas páginas do menu", () => {
  for (const item of NAV_ITEMS.filter((i) => i.implemented)) {
    test(`axe ${item.href}`, async ({ page }) => {
      await page.goto(item.href);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await settle(page);
      expect(await seriousViolations(page)).toEqual([]);
    });
  }
});
