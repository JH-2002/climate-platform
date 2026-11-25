/**
 * Roteiro de gravação da vitrine (spec 012, FR-195, ADR-017).
 *
 * Percorre a plataforma como um visitante e grava cada resposta 200 da API em
 * DEMO_OUT/<arquivo de lib/demo.ts>. A vitrine lê exatamente o que a interface pediu aqui.
 * Rotas de detalhe que dependem de clique (setores, bacias, alertas) são completadas a partir
 * das listas gravadas. Cada cenário pronto do Laboratório é simulado.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page, type Response } from "@playwright/test";
import { ALL_LAYERS } from "../features/map/state";
import { NAV_ITEMS } from "../features/navigation/registry";
import { demoFile } from "../lib/demo";

const OUT = path.resolve(process.env.DEMO_OUT ?? path.join(__dirname, "..", "demo-out"));
const API = process.env.DEMO_API_URL ?? "http://localhost:8000";
const counts = { files: 0, bytes: 0 };
/** GETs da API que a interface pediu e os que ficaram gravados: o que faltar é buscado no fim. */
const requested = new Set<string>();
const saved = new Set<string>();

function save(file: string, body: Buffer) {
  const target = path.join(OUT, file);
  if (!target.startsWith(OUT + path.sep)) throw new Error(`Caminho fora da saída: ${file}`);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  if (!fs.existsSync(target)) counts.files += 1;
  saved.add(file);
  fs.writeFileSync(target, body);
  counts.bytes += body.length;
}

async function record(response: Response) {
  const request = response.request();
  const url = new URL(response.url());
  // Qualquer 2xx: a criação de uma simulação responde 201.
  if (!url.pathname.startsWith("/api/v1/") || response.status() < 200 || response.status() >= 300) return;
  const method = request.method();
  if (method !== "GET" && method !== "POST") return;
  const body = method === "POST" ? (request.postDataJSON() as unknown) : undefined;
  const file = demoFile(method, `${url.pathname}${url.search}`, body);
  if (!file) return;
  try {
    save(file, await response.body());
  } catch {
    // corpo indisponível (navegação cancelada): a próxima resposta da mesma rota grava
  }
}

/** Grava uma rota pedida direto à API (detalhes que a interface só pede depois de um clique). */
async function fetchAndSave(page: Page, apiPath: string): Promise<unknown> {
  const response = await page.request.get(`${API}${apiPath}`);
  if (response.status() !== 200) return null;
  const file = demoFile("GET", apiPath);
  const body = await response.body();
  if (file) save(file, body);
  return (response.headers()["content-type"] ?? "").includes("json") ? (JSON.parse(body.toString("utf8")) as unknown) : null;
}

/** Várias rotas de detalhe de uma vez (o roteiro em série estourava o tempo com 793 setores). */
async function fetchAll(page: Page, paths: string[], parallel = 8) {
  let next = 0;
  const worker = async () => {
    while (next < paths.length) {
      const apiPath = paths[next++]!;
      await fetchAndSave(page, apiPath).catch(() => undefined);
    }
  };
  await Promise.all(Array.from({ length: parallel }, worker));
}

async function settle(page: Page, extra = 1500) {
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
  await page.waitForTimeout(extra);
}

async function visit(page: Page, url: string, extra?: number) {
  await page.goto(url);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 30_000 });
  await settle(page, extra);
}

// A pasta de saída é limpa pelo workflow, uma vez: se o Playwright reiniciar depois de uma
// falha, o que já foi gravado continua lá.
test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test.beforeEach(({ page }) => {
  page.on("response", (response) => void record(response));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() === "GET" && url.pathname.startsWith("/api/v1/")) requested.add(`${url.pathname}${url.search}`);
  });
});

test("páginas do menu", async ({ page }) => {
  for (const item of NAV_ITEMS.filter((i) => i.implemented)) {
    await visit(page, item.href);
  }
});

test("mapa com todas as camadas, em 3D e em 2D", async ({ page }) => {
  const all = ALL_LAYERS.join(",");
  await visit(page, `/map?modo=3d&camadas=${all}`, 5000);
  await visit(page, `/map?modo=2d&camadas=${all}`, 5000);
});

test("risco: categorias, subprefeituras e detalhes de todos os setores", async ({ page }) => {
  await visit(page, "/risk");
  const category = page.getByRole("combobox", { name: "Categoria" });
  for (const value of await category.locator("option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value))) {
    await category.selectOption(value);
    await settle(page, 500);
  }
  await category.selectOption("");
  const sub = page.getByRole("combobox", { name: "Subprefeitura" });
  for (const value of await sub.locator("option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value))) {
    await sub.selectOption(value);
    await settle(page, 300);
  }
  await sub.selectOption("");
  await settle(page);
  // Detalhe e terreno de cada setor: a explicação ("Por quê?") pede os dois.
  const layer = (await fetchAndSave(page, "/api/v1/map/layers/risk")) as { features?: { properties?: { id?: number } }[] };
  const ids = (layer?.features ?? []).flatMap((f) => (f.properties?.id === undefined ? [] : [f.properties.id]));
  await fetchAll(
    page,
    ids.flatMap((id) => [`/api/v1/risk/areas/${id}`, `/api/v1/geo/sectors/${id}/terrain`]),
  );
  // Uma explicação aberta pela interface (pela URL, como num link compartilhado).
  if (ids[0] !== undefined) await visit(page, `/risk?setor=${ids[0]}`);
});

test("alertas: detalhes dos alertas oficiais", async ({ page }) => {
  await visit(page, "/alerts");
  const active = (await fetchAndSave(page, "/api/v1/alerts/active")) as { official?: { id: number }[] };
  await fetchAll(page, (active?.official ?? []).map((a) => `/api/v1/alerts/official/${a.id}`));
  for (const alert of (active?.official ?? []).slice(0, 5)) {
    await visit(page, `/alerts?alerta=${alert.id}`, 500);
  }
});

test("análises: todas as abas", async ({ page }) => {
  for (const aba of ["chuva", "tendencias", "risco", "fontes", "studio"]) {
    await visit(page, `/analytics?aba=${aba}`, 2500);
  }
  await visit(page, "/analytics/datasets", 2500);
});

test("geointeligência: bacias, ficha e bloco 3D", async ({ page }) => {
  for (const ordem of ["alto", "setores", "ocorrencias", "piscinoes", "nome"]) {
    await visit(page, `/geo-3d?aba=bacias&ordem=${ordem}`, 500);
  }
  const list = (await fetchAndSave(page, "/api/v1/geo/basins?ordem=alto")) as { items?: { id: number }[] };
  const basins = list?.items ?? [];
  await fetchAll(page, basins.map((b) => `/api/v1/geo/basins/${b.id}`));
  // Bloco 3D (com os blocos do relevo) para as bacias mais críticas.
  for (const basin of basins.slice(0, 5)) {
    await visit(page, `/geo-3d?aba=bloco&bacia=${basin.id}`, 6000);
  }
  if (basins[0]) await visit(page, `/geo-3d?aba=bacias&bacia=${basins[0].id}`, 3000);
});

test("laboratório: cada cenário pronto simulado", async ({ page }) => {
  await visit(page, "/simulation");
  const presets = page.getByRole("group", { name: "Cenários prontos" }).getByRole("button");
  const total = await presets.count();
  for (let i = 0; i < total; i++) {
    await visit(page, "/simulation");
    await presets.nth(i).click();
    await page.getByRole("button", { name: "Simular" }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Resultado da simulação" })).toBeVisible({ timeout: 180_000 });
    await settle(page, 3000);
  }
  await visit(page, "/simulation");
});

// Respostas que a página não chegou a ler (navegação seguiu antes de o corpo chegar).
test("completar o que a interface pediu e não ficou gravado", async ({ page }) => {
  const missing = [...requested].filter((apiPath) => {
    const file = demoFile("GET", apiPath);
    return file !== null && !saved.has(file);
  });
  console.log(`Pedidos sem gravação: ${missing.length}`);
  await fetchAll(page, missing);
});

test.afterAll(() => {
  const meta = { recorded_at: new Date().toISOString(), files: counts.files };
  fs.writeFileSync(path.join(OUT, "meta.json"), JSON.stringify(meta));
  console.log(`Gravação: ${counts.files} arquivos, ${(counts.bytes / 1e6).toFixed(1)} MB escritos.`);
});
