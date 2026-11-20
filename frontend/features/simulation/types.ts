import type { RiskCategory, RiskFactor } from "@/features/risk/types";

export type Pattern = "CONSTANT" | "PEAKED" | "SHARP";

export interface CellInput {
  latitude: number;
  longitude: number;
  radius_km: number;
}

export interface ScenarioInput {
  total_mm: number;
  duration_h: number;
  pattern: Pattern;
  antecedent_mm: number;
  cell: CellInput | null;
}

export type SimulationMode = "SIMULATION" | "HYBRID";

/** Modo, variações e seed (Parte B). Fica junto do cenário no formulário e na URL. */
export interface RunOptions {
  mode: SimulationMode;
  multiplier: number;
  add_storm: boolean;
  members: number;
  intensity_pct: number;
  shift_km: number;
  seed: number | null;
}

export interface StoredScenario extends ScenarioInput {
  hybrid: { multiplier: number; add_storm: boolean } | null;
  uncertainty: { members: number; intensity_pct: number; shift_km: number } | null;
}

export interface EnsembleSummary {
  members: number;
  mean: number;
  p10: number;
  p90: number;
  minimum: number;
  maximum: number;
}

export interface RepeatCheck {
  original_id: string;
  same_engine_versions: boolean;
  same_sectors: boolean;
  same_forecast: boolean | null;
  identical_results: boolean;
}

export interface RunListItem {
  id: string;
  created_at: string;
  mode: SimulationMode;
  scenario_text: string;
  preset: string | null;
  seed: number | null;
  members: number;
  high_or_above: number;
  unknown: number;
}

export interface Preset {
  code: string;
  name: string;
  description: string;
  origin: string;
  scenario: ScenarioInput;
}

export interface Center {
  name: string;
  latitude: number;
  longitude: number;
  sectors: number;
}

export interface SubprefectureChange {
  name: string;
  sectors: number;
  high_or_above_simulated: number;
  high_or_above_real: number;
  raised: number;
}

export interface Comparison {
  real_run: { id: number; computed_at: string; stale: boolean } | null;
  real_counts: Record<RiskCategory, number>;
  raised: number;
  lowered: number;
  unchanged: number;
  not_comparable: number;
  subprefectures: SubprefectureChange[];
}

export interface SimulationRun {
  id: string;
  created_at: string;
  kind: "SIMULATED";
  mode: SimulationMode;
  scenario: StoredScenario;
  scenario_text: string;
  preset: string | null;
  seed: number | null;
  members: number;
  simulation_engine_version: string;
  risk_engine_version: string;
  sectors_fingerprint: string;
  sectors_changed: boolean;
  sector_count: number;
  counts: Record<RiskCategory, number>;
  comparison: Comparison;
  duration_ms: number;
  forecast_issued_at: string | null;
  ensemble: EnsembleSummary | null;
  repeat_of: string | null;
  repeat_check: RepeatCheck | null;
  banner: string;
  disclaimer: string;
}

export interface SimulatedSector {
  id: number;
  code: string;
  name: string | null;
  subprefecture: string | null;
  grade: number;
  households: number | null;
  category: RiskCategory;
  real_category: RiskCategory | null;
  rain_level: number | null;
  susceptibility: number;
  p1h_max_mm: number | null;
  p24_mm: number | null;
  a72_mm: number | null;
  rain_factor: number;
  distance_km: number | null;
  p_high: number | null;
  p_critical: number | null;
  factors: RiskFactor[];
}

export interface SimulatedSectorPage {
  items: SimulatedSector[];
  total: number;
  limit: number;
  offset: number;
  subprefectures: string[];
  banner: string;
  disclaimer: string;
}

export interface SimulationLayerProps {
  id: number;
  code: string;
  name: string | null;
  subprefecture: string | null;
  grade: number;
  category: RiskCategory;
  rain_level: number | null;
  p1h_max_mm: number | null;
  p24_mm: number | null;
  kind: "SIMULATED";
}
