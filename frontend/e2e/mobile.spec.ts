import { NAV_ITEMS } from "../features/navigation/registry";
import { expect, RECORD, seriousViolations, test } from "./api";

/** Testes em tela de celular (spec 013, FR-205). Reaproveitam as gravações dos testes de computador. */

test.skip(RECORD, "Os testes de celular usam as gravações dos testes de computador.");

test.describe("menu recolhível", () => {
  test.use({ recording: "axe /" });

  test("abre, navega e fecha com Esc", async ({ page }) => {
    await page.goto("/");
    const menu = page.getByRole("button", { name: /^Menu/ });
    await expect(menu).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Navegação principal" }).getByRole("link", { name: "Relatórios" })).toBeHidden();

    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Escape");
    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await expect(menu).toBeFocused();

    await menu.click();
    await page.getByRole("navigation", { name: "Navegação principal" }).getByRole("link", { name: "Estado do sistema" }).click();
    await expect(page).toHaveURL(/\/status/);
    await expect(menu).toHaveAttribute("aria-expanded", "false");
  });

  test("manifesto e service worker são servidos", async ({ page, request }) => {
    await page.goto("/");
    const href = await page.locator('link[rel="manifest"]').getAttribute("href");
    expect(href).toBeTruthy();
    const manifest = await request.get(href!);
    expect(manifest.status()).toBe(200);
    expect((await manifest.json()) as { short_name: string }).toMatchObject({ short_name: "Clima SP" });
    expect((await request.get("/sw.js")).status()).toBe(200);
  });
});

for (const item of NAV_ITEMS.filter((i) => i.implemented)) {
  test.describe(`celular ${item.href}`, () => {
    test.use({ recording: `axe ${item.href}` });

    test(`celular ${item.href}: título à vista, sem rolagem lateral e axe`, async ({ page }) => {
      await page.goto(item.href);
      const title = page.getByRole("heading", { level: 1 });
      await expect(title).toBeVisible();
      // AC-200: o título aparece sem rolar.
      const box = await title.boundingBox();
      const viewport = page.viewportSize()!;
      expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
      await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
      // FR-201: nada mais largo que a tela.
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, "largura além da tela (px)").toBeLessThanOrEqual(1);
      expect(await seriousViolations(page)).toEqual([]);
    });
  });
}
