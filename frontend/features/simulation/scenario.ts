/**
 * Cenário de simulação no formulário e na URL (spec 007). As faixas espelham o backend
 * (BR-104): a API confere de novo e é a palavra final.
 */

import type { CellInput, Pattern, ScenarioInput } from "./types";

export const LIMITS = {
  total_mm: [1, 300],
  duration_h: [1, 24],
  antecedent_mm: [0, 300],
  radius_km: [2, 30],
} as const;

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
  return {
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
  if (state.sectorId !== null) params.set("setor", String(state.sectorId));
  return params.toString();
}

function within(value: number, [low, high]: readonly [number, number]): boolean {
  return Number.isFinite(value) && value >= low && value <= high;
}

/** Mensagens por campo, em português; vazio = cenário válido. */
export function validateScenario(s: ScenarioInput): Partial<Record<"total" | "duration" | "antecedent" | "radius", string>> {
  const errors: Partial<Record<"total" | "duration" | "antecedent" | "radius", string>> = {};
  if (!within(s.total_mm, LIMITS.total_mm)) errors.total = "Informe de 1 a 300 mm.";
  if (!within(s.duration_h, LIMITS.duration_h) || !Number.isInteger(s.duration_h))
    errors.duration = "Informe de 1 a 24 horas, em horas inteiras.";
  if (!within(s.antecedent_mm, LIMITS.antecedent_mm)) errors.antecedent = "Informe de 0 a 300 mm.";
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
