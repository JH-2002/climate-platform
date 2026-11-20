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
  mode: "SIMULATION" | "HYBRID";
  scenario: ScenarioInput;
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
