/**
 * Modo demonstração (spec 012, ADR-017): a vitrine estática no GitHub Pages lê as respostas da
 * API de arquivos gravados. O mesmo módulo dá nome aos arquivos na gravação (Playwright) e na
 * leitura (cliente da API), então os dois lados nunca divergem. Funções puras.
 */

const API_PREFIX = "/api/v1/";
export const DEMO_DIR = "demo-data";

export const DEMO_MESSAGES = {
  unavailable: "Indisponível na demonstração pública.",
  simulation:
    "Na demonstração pública só os cenários prontos podem ser simulados. Para simular outros valores, rode a plataforma (veja o README).",
  reports: "A geração de relatórios precisa da plataforma rodando (veja o README).",
} as const;

/** Lido a cada chamada: os testes trocam a variável; no build o Next fixa o valor. */
export function demoEnabled(): boolean {
  return process.env.NEXT_PUBLIC_DEMO === "1";
}

/** Prefixo do site no GitHub Pages (`/climate-platform`), vazio fora dele. */
export function basePath(): string {
  return (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/+$/, "");
}

/** FNV-1a de 32 bits sobre os bytes UTF-8, em 8 dígitos hexadecimais. */
export function fnv1a(text: string): string {
  let hash = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(text)) {
    hash ^= byte;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

/** Consulta em forma única: pares ordenados por nome e valor, codificados como no `encodeURIComponent`. */
export function canonicalQuery(search: string): string {
  const pairs = [...new URLSearchParams(search.replace(/^\?/, "")).entries()];
  pairs.sort(([ka, va], [kb, vb]) => (ka === kb ? (va < vb ? -1 : va > vb ? 1 : 0) : ka < kb ? -1 : 1));
  return pairs.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
}

/** JSON com as chaves dos objetos ordenadas, para o corpo de um POST virar sempre o mesmo texto. */
export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${canonicalJson(v)}`).join(",")}}`;
  }
  return JSON.stringify(value ?? null);
}

function split(pathWithQuery: string): { path: string; query: string } | null {
  const [rawPath = "", ...rest] = pathWithQuery.split("?");
  const path = rawPath.replace(/^https?:\/\/[^/]+/, "");
  if (!path.startsWith(API_PREFIX)) return null;
  const relative = path.slice(API_PREFIX.length).replace(/\/+$/, "");
  if (!relative || relative.split("/").some((s) => s === ".." || s === ".")) return null;
  return { path: relative, query: canonicalQuery(rest.join("?")) };
}

/** Último trecho com extensão (`relief.png`, `series.csv`): o arquivo gravado guarda o conteúdo como veio. */
function binaryName(path: string): { dir: string; stem: string; ext: string } | null {
  const slash = path.lastIndexOf("/");
  const name = path.slice(slash + 1);
  const dot = name.lastIndexOf(".");
  if (dot <= 0) return null;
  return { dir: path.slice(0, slash + 1), stem: name.slice(0, dot), ext: name.slice(dot) };
}

/**
 * Arquivo (relativo a `demo-data/`) de uma chamada da API, ou null se não for da API.
 * GET sem consulta: `<caminho>/index.json`; com consulta: `<caminho>/q-<hash>.json`;
 * caminho com extensão: o próprio nome (`<nome>.q-<hash><ext>` com consulta);
 * POST: `<caminho>/post-<hash do corpo>.json`.
 */
export function demoFile(method: "GET" | "POST", pathWithQuery: string, body?: unknown): string | null {
  const parts = split(pathWithQuery);
  if (!parts) return null;
  const { path, query } = parts;
  if (method === "POST") return `${path}/post-${fnv1a(canonicalJson(body))}.json`;
  const binary = binaryName(path);
  if (binary) {
    return query ? `${binary.dir}${binary.stem}.q-${fnv1a(query)}${binary.ext}` : path;
  }
  return query ? `${path}/q-${fnv1a(query)}.json` : `${path}/index.json`;
}

/** A mesma chamada sem a consulta: resposta de reserva quando a consulta exata não foi gravada. */
export function demoFallbackFile(pathWithQuery: string): string | null {
  const parts = split(pathWithQuery);
  if (!parts?.query) return null;
  return demoFile("GET", `${API_PREFIX}${parts.path}`);
}

export function demoUrl(file: string): string {
  return `${basePath()}/${DEMO_DIR}/${file}`;
}

/** Mensagem de uma escrita sem resposta gravada. */
export function demoWriteMessage(pathWithQuery: string): string {
  const path = split(pathWithQuery)?.path ?? "";
  if (path.startsWith("simulation")) return DEMO_MESSAGES.simulation;
  if (path.startsWith("reports")) return DEMO_MESSAGES.reports;
  return DEMO_MESSAGES.unavailable;
}

/** URL para `<img>`, blocos do mapa e downloads que não passam pelo cliente da API. */
export function assetUrl(apiPath: string): string {
  if (!demoEnabled()) return apiPath;
  const file = demoFile("GET", apiPath);
  return file ? demoUrl(file) : apiPath;
}
