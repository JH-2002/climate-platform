/**
 * Estado do Analytics Studio ↔ URL e compatibilidade de visualizações (FR-094, AC-086).
 * Funções puras: a interface só oferece o que o catálogo declara e o agrupamento permite.
 */

import type { DatasetInfo } from "./types";

export type Viz = "line" | "bar" | "area" | "histogram" | "box" | "calendar" | "ranking" | "table";

export interface StudioState {
  dataset: string;
  variable: string;
  location: string | null;
  start: string;
  end: string;
  grain: string;
  agg: string;
  compare: string | null;
  viz: Viz;
}

export const VIZ_LABELS: Record<Viz, string> = {
  line: "Linha",
  bar: "Barras",
  area: "Área",
  histogram: "Histograma",
  box: "Caixa (quartis)",
  calendar: "Calendário",
  ranking: "Ranking por local",
  table: "Tabela",
};

export const GRAIN_LABELS: Record<string, string> = {
  day: "Dia",
  week: "Semana",
  month: "Mês",
  year: "Ano",
};

export const AGG_LABELS: Record<string, string> = {
  sum: "Soma",
  mean: "Média",
  min: "Mínimo",
  max: "Máximo",
  count: "Contagem",
};

export const COMPARE_LABELS: Record<string, string> = {
  normal: "Normal 1991–2020",
  previous_period: "Período anterior",
  same_period_last_year: "Mesmo período do ano anterior",
};

interface ParamsLike {
  get(name: string): string | null;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function defaultState(dataset: DatasetInfo, today: string): StudioState {
  const variable = dataset.variables[0];
  const end = periodEnd(dataset.period_end, today);
  const grain = dataset.grains.includes("month") ? "month" : dataset.grains[0] ?? "day";
  const candidate = grain === "month" ? `${Number(end.slice(0, 4)) - 2}-01-01` : shiftDays(end, -30);
  const first = dataset.period_start ? periodStart(dataset.period_start) : null;
  return {
    dataset: dataset.id,
    variable: variable?.code ?? "",
    location: dataset.locations[0]?.key ?? null,
    start: first && first > candidate ? first : candidate,
    end,
    grain,
    agg: variable?.aggregations[0] ?? "mean",
    compare: null,
    viz: (dataset.visualizations[0] as Viz) ?? "table",
  };
}

/** "2025-12" → último dia do mês; "2026-11-26T02:00:00+00:00" → "2026-11-26". */
function periodEnd(value: string | null, today: string): string {
  if (!value) return today;
  if (/^\d{4}-\d{2}$/.test(value)) {
    const [y, m] = value.split("-").map(Number) as [number, number];
    return new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10);
  }
  const day = value.slice(0, 10);
  return ISO_DATE.test(day) ? day : today;
}

function periodStart(value: string): string {
  return /^\d{4}-\d{2}$/.test(value) ? `${value}-01` : value.slice(0, 10);
}

function shiftDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Visualizações oferecidas para o conjunto e o agrupamento escolhidos (AC-086). */
export function compatibleVisualizations(dataset: DatasetInfo, grain: string): Viz[] {
  return (dataset.visualizations as Viz[]).filter((viz) => {
    if (viz === "calendar") return grain === "day";
    if (viz === "histogram" || viz === "box") return dataset.numeric;
    if (viz === "ranking") return dataset.locations.length > 1;
    return true;
  });
}

/** Comparações que fazem sentido: normal só para séries com climatologia, mês ou ano. */
export function compatibleComparisons(dataset: DatasetInfo, grain: string): string[] {
  const options = ["previous_period", "same_period_last_year"];
  if ((dataset.id === "iag-rain-monthly" || dataset.id === "reanalysis-daily") && (grain === "month" || grain === "year")) {
    options.unshift("normal");
  }
  return options;
}

export function parseStudio(params: ParamsLike, datasets: DatasetInfo[], today: string): StudioState | null {
  const dataset = datasets.find((d) => d.id === params.get("conjunto")) ?? datasets[0];
  if (!dataset) return null;
  const base = defaultState(dataset, today);
  const variable = dataset.variables.find((v) => v.code === params.get("variavel")) ?? dataset.variables[0];
  const grain = dataset.grains.includes(params.get("agrupar") ?? "") ? (params.get("agrupar") as string) : base.grain;
  const agg = variable?.aggregations.includes(params.get("agregacao") ?? "") ? (params.get("agregacao") as string) : (variable?.aggregations[0] ?? base.agg);
  const location = dataset.locations.some((l) => l.key === params.get("local")) ? params.get("local") : base.location;
  const start = ISO_DATE.test(params.get("inicio") ?? "") ? (params.get("inicio") as string) : base.start;
  const end = ISO_DATE.test(params.get("fim") ?? "") ? (params.get("fim") as string) : base.end;
  const compare = compatibleComparisons(dataset, grain).includes(params.get("comparar") ?? "") ? params.get("comparar") : null;
  const vizOptions = compatibleVisualizations(dataset, grain);
  const viz = vizOptions.includes(params.get("visual") as Viz) ? (params.get("visual") as Viz) : (vizOptions[0] ?? "table");
  return { dataset: dataset.id, variable: variable?.code ?? "", location, start, end, grain, agg, compare, viz };
}

export function serializeStudio(state: StudioState): string {
  const params = new URLSearchParams({
    aba: "studio",
    conjunto: state.dataset,
    variavel: state.variable,
    inicio: state.start,
    fim: state.end,
    agrupar: state.grain,
    agregacao: state.agg,
    visual: state.viz,
  });
  if (state.location) params.set("local", state.location);
  if (state.compare) params.set("comparar", state.compare);
  return params.toString();
}

/** Muda o conjunto: volta aos padrões dele (variável, local, agrupamento) para não misturar. */
export function switchDataset(dataset: DatasetInfo, today: string): StudioState {
  return defaultState(dataset, today);
}

/** Histograma de faixas de largura igual (pura): usado pela visualização "Histograma". */
export function equalBins(values: number[], count = 10): { low: number; high: number; n: number }[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [{ low: min, high: max, n: values.length }];
  const width = (max - min) / count;
  const bins = Array.from({ length: count }, (_, i) => ({ low: min + i * width, high: min + (i + 1) * width, n: 0 }));
  for (const v of values) {
    const index = Math.min(count - 1, Math.floor((v - min) / width));
    bins[index]!.n += 1;
  }
  return bins;
}
