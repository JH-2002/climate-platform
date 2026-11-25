/** Formulário de relatório: padrão, leitura da URL e parâmetros da API. Funções puras. */

import type { ReportForm, ReportFormat, ReportType } from "./types";

const TYPES: readonly ReportType[] = ["situacao", "risco", "alertas", "chuva", "simulacao"];
const FORMATS: readonly ReportFormat[] = ["pdf", "csv", "json"];

interface ParamsLike {
  get(name: string): string | null;
}

function isoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function defaultForm(today: Date): ReportForm {
  const weekAgo = new Date(today.getTime() - 7 * 86_400_000);
  return {
    type: "situacao",
    format: "pdf",
    subprefecture: "",
    since: isoDay(weekAgo),
    until: isoDay(today),
    category: "",
    point: "",
    grain: "month",
    simulationId: "",
  };
}

/** Atalhos das outras páginas: /reports?tipo=risco&subprefeitura=PENHA&formato=csv. */
export function formFromUrl(params: ParamsLike, today: Date): ReportForm {
  const form = defaultForm(today);
  const type = params.get("tipo");
  if (type && (TYPES as readonly string[]).includes(type)) form.type = type as ReportType;
  const format = params.get("formato");
  if (format && (FORMATS as readonly string[]).includes(format)) form.format = format as ReportFormat;
  form.subprefecture = params.get("subprefeitura") ?? "";
  form.category = params.get("categoria") ?? "";
  form.point = params.get("ponto") ?? "";
  form.simulationId = params.get("simulacao") ?? "";
  const grain = params.get("agregacao");
  if (grain === "day" || grain === "month" || grain === "year") form.grain = grain;
  const since = params.get("desde");
  const until = params.get("ate");
  if (since && /^\d{4}-\d{2}-\d{2}$/.test(since)) form.since = since;
  if (until && /^\d{4}-\d{2}-\d{2}$/.test(until)) form.until = until;
  return form;
}

export function apiParams(form: ReportForm): Record<string, unknown> {
  switch (form.type) {
    case "situacao":
      return {};
    case "risco":
      return form.subprefecture ? { subprefecture: form.subprefecture } : {};
    case "alertas":
      return { since: form.since, until: form.until, ...(form.category ? { category: form.category } : {}) };
    case "chuva":
      return { since: form.since, until: form.until, grain: form.grain, ...(form.point ? { point: form.point } : {}) };
    case "simulacao":
      return { simulation_id: form.simulationId };
  }
}

export function reportHref(type: ReportType, extra: Record<string, string> = {}): string {
  return `/reports?${new URLSearchParams({ tipo: type, ...extra })}`;
}

export const STATUS_LABELS = {
  QUEUED: "Na fila",
  RUNNING: "Gerando…",
  DONE: "Pronto",
  FAILED: "Falhou",
  EXPIRED: "Expirado (passou de 7 dias)",
} as const;

export function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}
