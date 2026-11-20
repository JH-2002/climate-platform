/**
 * Cenário de simulação no formulário e na URL (spec 007). As faixas espelham o backend
 * (BR-104): a API confere de novo e é a palavra final.
 */

import type { CellInput, Pattern, RunOptions, ScenarioInput, SimulationRun } from "./types";

export const LIMITS = {
  total_mm: [1, 300],
  duration_h: [1, 24],
  antecedent_mm: [0, 300],
  radius_km: [2, 30],
  multiplier_pct: [50, 300],
  members: [1, 100],
  intensity_pct: [0, 50],
  shift_km: [0, 10],
  seed: [0, 2 ** 31 - 1],
} as const;

export const DEFAULT_OPTIONS: RunOptions = {
  mode: "SIMULATION",
  multiplier: 1,
  add_storm: false,
  members: 1,
  intensity_pct: 20,
  shift_km: 3,
  seed: null,
};

export const PATTERN_LABELS: Record<Pattern, string> = {
  CONSTANT: "Constante",
  PEAKED: "Concentrada (50% na hora de pico)",
  SHARP: "Muito concentrada (70% na hora de pico)",
};

/** Praça da Sé: centro padrão da célula. */
export const DEFAULT_CENTER = { latitude: -23.5505, longitude: -46.6333 };

export const DEFAULT_SCENARIO: ScenarioInput = {
  total_mm: 40,
  duration_h: 1,
  pattern: "CONSTANT",
  antecedent_mm: 0,
  cell: { ...DEFAULT_CENTER, radius_km: 6 },
};

export interface SimulationState {
  scenario: ScenarioInput;
  options: RunOptions;
  preset: string | null;
  runId: string | null;
  sectorId: number | null;
}

function num(params: URLSearchParams, key: string): number | null {
  const raw = params.get(key);
  if (raw === null || raw.trim() === "") return null;
  const value = Number(raw.replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

function isPattern(value: string | null): value is Pattern {
  return value === "CONSTANT" || value === "PEAKED" || value === "SHARP";
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseSimulationState(params: URLSearchParams): SimulationState {
  const d = DEFAULT_SCENARIO;
  const area = params.get("area");
  const lat = num(params, "lat");
  const lon = num(params, "lon");
  const radius = num(params, "raio");
  const cell: CellInput | null =
    area === "cidade"
      ? null
      : {
          latitude: lat ?? d.cell!.latitude,
          longitude: lon ?? d.cell!.longitude,
          radius_km: radius ?? d.cell!.radius_km,
        };
  const pattern = params.get("padrao");
  const runId = params.get("execucao");
  const sector = num(params, "setor");
  const o = DEFAULT_OPTIONS;
  const seed = num(params, "seed");
  const options: RunOptions = {
    mode: params.get("modo") === "hibrido" ? "HYBRID" : "SIMULATION",
    multiplier: (num(params, "mult") ?? o.multiplier * 100) / 100,
    add_storm: params.get("tempestade") === "1",
    members: num(params, "variacoes") ?? o.members,
    intensity_pct: num(params, "intensidade") ?? o.intensity_pct,
    shift_km: num(params, "deslocamento") ?? o.shift_km,
    seed: seed !== null && Number.isInteger(seed) ? seed : null,
  };
  return {
    options,
    scenario: {
      total_mm: num(params, "total") ?? d.total_mm,
      duration_h: num(params, "duracao") ?? d.duration_h,
      pattern: isPattern(pattern) ? pattern : d.pattern,
      antecedent_mm: num(params, "antecedente") ?? d.antecedent_mm,
      cell,
    },
    preset: params.get("cenario"),
    runId: runId && UUID.test(runId) ? runId : null,
    sectorId: sector !== null && Number.isInteger(sector) ? sector : null,
  };
}

export function serializeSimulationState(state: SimulationState): string {
  const s = state.scenario;
  const params = new URLSearchParams();
  if (state.runId) params.set("execucao", state.runId);
  if (state.preset) params.set("cenario", state.preset);
  params.set("total", String(s.total_mm));
  params.set("duracao", String(s.duration_h));
  params.set("padrao", s.pattern);
  params.set("antecedente", String(s.antecedent_mm));
  if (s.cell) {
    params.set("area", "celula");
    params.set("lat", s.cell.latitude.toFixed(4));
    params.set("lon", s.cell.longitude.toFixed(4));
    params.set("raio", String(s.cell.radius_km));
  } else {
    params.set("area", "cidade");
  }
  const o = state.options;
  if (o.mode === "HYBRID") {
    params.set("modo", "hibrido");
    params.set("mult", String(Math.round(o.multiplier * 100)));
    if (o.add_storm) params.set("tempestade", "1");
  }
  if (o.members > 1) {
    params.set("variacoes", String(o.members));
    params.set("intensidade", String(o.intensity_pct));
    params.set("deslocamento", String(o.shift_km));
    if (o.seed !== null) params.set("seed", String(o.seed));
  }
  if (state.sectorId !== null) params.set("setor", String(state.sectorId));
  return params.toString();
}

function within(value: number, [low, high]: readonly [number, number]): boolean {
  return Number.isFinite(value) && value >= low && value <= high;
}

export type FieldKey =
  | "total"
  | "duration"
  | "antecedent"
  | "radius"
  | "multiplier"
  | "members"
  | "intensity"
  | "shift"
  | "seed";

/** Os campos da chuva do cenário só valem quando ela entra na simulação. */
export function usesStorm(o: RunOptions): boolean {
  return o.mode === "SIMULATION" || o.add_storm;
}

/** Mensagens por campo, em português; vazio = cenário válido. */
export function validateScenario(s: ScenarioInput, o: RunOptions = DEFAULT_OPTIONS): Partial<Record<FieldKey, string>> {
  const errors: Partial<Record<FieldKey, string>> = {};
  if (o.mode === "HYBRID" && !within(o.multiplier * 100, LIMITS.multiplier_pct)) errors.multiplier = "Informe de 50% a 300%.";
  if (!within(o.members, LIMITS.members) || !Number.isInteger(o.members)) errors.members = "Informe de 1 a 100 variações.";
  if (o.members > 1) {
    if (!within(o.intensity_pct, LIMITS.intensity_pct)) errors.intensity = "Informe de 0% a 50%.";
    if (!within(o.shift_km, LIMITS.shift_km)) errors.shift = "Informe de 0 a 10 km.";
    if (o.seed !== null && (!within(o.seed, LIMITS.seed) || !Number.isInteger(o.seed)))
      errors.seed = "Informe um número inteiro de 0 a 2147483647.";
  }
  if (!usesStorm(o)) return errors;
  if (!within(s.total_mm, LIMITS.total_mm)) errors.total = "Informe de 1 a 300 mm.";
  if (!within(s.duration_h, LIMITS.duration_h) || !Number.isInteger(s.duration_h))
    errors.duration = "Informe de 1 a 24 horas, em horas inteiras.";
  if (o.mode === "SIMULATION" && !within(s.antecedent_mm, LIMITS.antecedent_mm))
    errors.antecedent = "Informe de 0 a 300 mm.";
  if (s.cell && !within(s.cell.radius_km, LIMITS.radius_km)) errors.radius = "Informe de 2 a 30 km.";
  return errors;
}

/** Chuva da hora mais forte, igual ao backend: nunca abaixo da média nem acima do total. */
export function peakHourMm(s: ScenarioInput): number {
  if (s.duration_h <= 1) return s.total_mm;
  const share = s.pattern === "SHARP" ? 0.7 : s.pattern === "PEAKED" ? 0.5 : 0;
  return Math.min(s.total_mm, Math.max(s.total_mm / s.duration_h, share * s.total_mm));
}

export function simulationHref(runId: string): string {
  return `/simulation?execucao=${runId}`;
}

/** Corpo da requisição para a API. */
export function requestBody(
  scenario: ScenarioInput,
  options: RunOptions,
  preset: string | null,
  repeatOf: string | null = null,
): Record<string, unknown> {
  const many = options.members > 1;
  return {
    ...scenario,
    mode: options.mode,
    multiplier: options.multiplier,
    add_storm: options.add_storm,
    members: options.members,
    intensity_pct: many ? options.intensity_pct : 0,
    shift_km: many ? options.shift_km : 0,
    seed: many ? options.seed : null,
    preset,
    repeat_of: repeatOf,
  };
}

/** Parâmetros de uma execução gravada, para repetir ou abrir no formulário. */
export function fromRun(run: SimulationRun): { scenario: ScenarioInput; options: RunOptions } {
  const s = run.scenario;
  return {
    scenario: {
      total_mm: s.total_mm,
      duration_h: s.duration_h,
      pattern: s.pattern,
      antecedent_mm: s.antecedent_mm,
      cell: s.cell ? { ...s.cell } : null,
    },
    options: {
      mode: run.mode,
      multiplier: s.hybrid?.multiplier ?? 1,
      add_storm: s.hybrid?.add_storm ?? false,
      members: s.uncertainty?.members ?? 1,
      intensity_pct: s.uncertainty?.intensity_pct ?? DEFAULT_OPTIONS.intensity_pct,
      shift_km: s.uncertainty?.shift_km ?? DEFAULT_OPTIONS.shift_km,
      seed: run.seed,
    },
  };
}

export function formatPercent(p: number | null): string {
  return p === null ? "—" : `${Math.round(p * 100)}%`;
}
