/**
 * API simulada para os testes ponta a ponta (spec 011, FR-179).
 *
 * Replay (padrão): cada teste lê e2e/fixtures/<teste>.json e responde às chamadas /api/v1/*
 * com as respostas gravadas, na mesma ordem (a última se repete, como numa consulta periódica).
 * O relógio do navegador fica parado no instante da gravação, e o que sai para a internet
 * (mapas de fundo, relevo) é cortado.
 *
 * Gravação (E2E_RECORD=1): os testes rodam contra a plataforma local e as respostas reais
 * são gravadas. Coleções grandes são cortadas para manter os arquivos pequenos.
 */
import fs from "node:fs";
import path from "node:path";
import { test as base, expect, type Page, type Response } from "@playwright/test";

export const RECORD = process.env.E2E_RECORD === "1";
const FIXTURES = path.join(__dirname, "fixtures");
const MAX_ITEMS = 60;
const MAX_BINARY = 300_000;

type Entry = {
  status: number;
  contentType: string;
  disposition?: string;
  json?: unknown;
  text?: string;
  base64?: string;
};
type Fixture = { recordedAt: string; responses: Record<string, Entry[]> };

function slug(title: string): string {
  return title
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function keysOf(method: string, url: URL): [string, string] {
  return [`${method} ${url.pathname}${url.search}`, `${method} ${url.pathname}`];
}

/** Corta coleções grandes (GeoJSON e listas) para o arquivo gravado não crescer demais. */
function trim(value: unknown): unknown {
  if (Array.isArray(value)) return value.slice(0, MAX_ITEMS);
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    for (const key of ["features", "items"]) {
      if (Array.isArray(obj[key])) obj[key] = (obj[key] as unknown[]).slice(0, MAX_ITEMS);
    }
  }
  return value;
}

async function toEntry(response: Response): Promise<Entry | null> {
  const headers = response.headers();
  const contentType = headers["content-type"] ?? "application/octet-stream";
  const entry: Entry = { status: response.status(), contentType };
  if (headers["content-disposition"]) entry.disposition = headers["content-disposition"];
  try {
    const body = await response.body();
    if (contentType.includes("json")) entry.json = trim(JSON.parse(body.toString("utf8")));
    else if (contentType.startsWith("text/")) entry.text = body.toString("utf8");
    else if (body.length <= MAX_BINARY) entry.base64 = body.toString("base64");
    else return null;
  } catch {
    return null; // corpo indisponível (redirecionamento, navegação cancelada)
  }
  return entry;
}

class Recorder {
  readonly responses: Record<string, Entry[]> = {};
  private pending: Promise<void>[] = [];

  attach(page: Page) {
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (!url.pathname.startsWith("/api/v1/")) return;
      const [exact, loose] = keysOf(response.request().method(), url);
      this.pending.push(
        toEntry(response).then((entry) => {
          if (!entry) return;
          (this.responses[exact] ??= []).push(entry);
          this.responses[loose] = [entry];
        }),
      );
    });
  }

  async save(file: string) {
    await Promise.all(this.pending);
    const fixture: Fixture = { recordedAt: new Date().toISOString(), responses: this.responses };
    fs.mkdirSync(FIXTURES, { recursive: true });
    fs.writeFileSync(file, JSON.stringify(fixture, null, 1) + "\n");
  }
}

export class MockApi {
  readonly missing: string[] = [];
  private readonly cursor = new Map<string, number>();
  private readonly overrides: [RegExp, (url: URL) => Entry][] = [];

  constructor(readonly fixture: Fixture) {}

  /** Troca a resposta de uma rota (para fixar um estado que a gravação pode não ter tido). */
  override(pattern: RegExp, json: unknown | ((url: URL) => unknown), status = 200) {
    this.overrides.unshift([
      pattern,
      (url) => ({
        status,
        contentType: "application/json",
        json: typeof json === "function" ? (json as (url: URL) => unknown)(url) : json,
      }),
    ]);
  }

  /** Respostas gravadas de uma rota, na ordem. */
  recorded(key: string): Entry[] {
    return this.fixture.responses[key] ?? [];
  }

  private next(method: string, url: URL): Entry | null {
    for (const [pattern, make] of this.overrides) {
      if (pattern.test(`${method} ${url.pathname}${url.search}`)) return make(url);
    }
    for (const key of keysOf(method, url)) {
      const list = this.fixture.responses[key];
      if (!list?.length) continue;
      const i = this.cursor.get(key) ?? 0;
      this.cursor.set(key, i + 1);
      return list[Math.min(i, list.length - 1)];
    }
    return null;
  }

  async install(page: Page) {
    await page.clock.setFixedTime(new Date(this.fixture.recordedAt));
    // Nada sai para a internet: estilos e blocos do mapa, relevo.
    await page.route(
      (url) => !["localhost", "127.0.0.1"].includes(url.hostname),
      (route) => route.abort("blockedbyclient"),
    );
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const entry = this.next(request.method(), url);
      if (!entry) {
        this.missing.push(`${request.method()} ${url.pathname}${url.search}`);
        await route.fulfill({
          status: 404,
          contentType: "application/problem+json",
          json: { title: "Não gravado", status: 404, detail: "Resposta ausente na gravação do E2E" },
        });
        return;
      }
      const headers: Record<string, string> = { "content-type": entry.contentType };
      if (entry.disposition) headers["content-disposition"] = entry.disposition;
      const body =
        entry.json !== undefined
          ? JSON.stringify(entry.json)
          : entry.base64 !== undefined
            ? Buffer.from(entry.base64, "base64")
            : (entry.text ?? "");
      await route.fulfill({ status: entry.status, headers, body });
    });
  }
}

type Fixtures = { api: MockApi; consoleErrors: string[] };

export const test = base.extend<Fixtures>({
  api: [
    async ({ page }, use, testInfo) => {
    const file = path.join(FIXTURES, `${slug(testInfo.title)}.json`);
    if (RECORD) {
      const recorder = new Recorder();
      recorder.attach(page);
      await use(new MockApi({ recordedAt: new Date().toISOString(), responses: {} }));
      await recorder.save(file);
      return;
    }
    if (!fs.existsSync(file)) {
      throw new Error(`Gravação ausente: ${path.relative(process.cwd(), file)} (veja e2e/README.md)`);
    }
    const api = new MockApi(JSON.parse(fs.readFileSync(file, "utf8")) as Fixture);
    await api.install(page);
    await use(api);
    },
    { auto: true },
  ],
  // Violação da CSP (FR-170) derruba o teste: o console avisa quando algo foi bloqueado.
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("console", (msg) => {
        if (/Content Security Policy|Refused to (load|execute|connect|apply|create)/i.test(msg.text())) {
          errors.push(msg.text());
        }
      });
      page.on("pageerror", (err) => errors.push(`Erro na página: ${err.message}`));
      await use(errors);
      expect(errors, "violações da CSP ou erros de script").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** axe-core (já dependência do projeto) injetado na página; só violações graves ou críticas. */
export async function seriousViolations(page: Page): Promise<string[]> {
  await page.addScriptTag({ path: path.join(__dirname, "..", "node_modules", "axe-core", "axe.min.js") });
  return page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: (ctx: unknown, opts: unknown) => Promise<{ violations: { id: string; impact: string | null; help: string; nodes: { target: unknown[] }[] }[] }> } }).axe;
    const result = await axe.run(
      { exclude: [[".maplibregl-canvas"]] },
      { resultTypes: ["violations"] },
    );
    return result.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id} (${v.impact}): ${v.help} — ${v.nodes.map((n) => JSON.stringify(n.target)).slice(0, 3).join(", ")}`);
  });
}
