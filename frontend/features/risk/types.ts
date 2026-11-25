/** Respostas de `/api/v1/risk/*` e camadas de risco do mapa (spec 005). */

export type RiskCategory = "LOW" | "MODERATE" | "HIGH" | "CRITICAL" | "UNKNOWN";

export interface RiskFactor {
  code: string;
  text: string;
  effect: "raises" | "info" | "unknown";
}

export interface RiskRunInfo {
  id: number;
  engine_version: string;
  computed_at: string;
  valid_until: string;
  forecast_issued_at: string | null;
  forecast_freshness: string;
  stale: boolean;
}

export interface RiskSummary {
  run: RiskRunInfo | null;
  counts: Record<RiskCategory, number>;
  sectors_freshness: string;
  disclaimer: string;
  attribution: string;
  experimental: boolean;
}

export interface RiskArea {
  id: number;
  code: string;
  name: string | null;
  subprefecture: string | null;
  basin: string | null;
  grade: number;
  households: number | null;
  category: RiskCategory;
  rain_level: number | null;
  susceptibility: number;
  p1h_max_mm: number | null;
  p24_mm: number | null;
  a72_mm: number | null;
  in_flood_extent_100y: boolean;
  nearby_occurrences_12m: number;
  factors: RiskFactor[];
  unknown_reason: string | null;
}

export interface RiskAreaPage {
  items: RiskArea[];
  total: number;
  limit: number;
  offset: number;
  subprefectures: string[];
  disclaimer: string;
}

export interface RiskInput {
  name: string;
  value: number | null;
  unit: string;
  kind: string;
  source: string;
}

export interface RiskOccurrence {
  type: string;
  occurred_on: string;
  subprefecture: string | null;
  distance_m: number;
}

export interface RiskAreaDetail extends RiskArea {
  processes: string[];
  inspected_on: string | null;
  latitude: number;
  longitude: number;
  forecast_point_key: string | null;
  forecast_distance_km: number | null;
  inputs: RiskInput[];
  nearby_occurrences: RiskOccurrence[];
  run: RiskRunInfo;
  official_url: string;
  disclaimer: string;
}

export interface NearestRiskArea {
  area: RiskArea | null;
  distance_m: number | null;
  max_distance_km: number;
  disclaimer: string;
}

export interface RiskLayerProps {
  id: number;
  code: string;
  name: string | null;
  subprefecture: string | null;
  grade: number;
  households: number | null;
  category: RiskCategory;
  rain_level: number | null;
  p1h_max_mm: number | null;
  p24_mm: number | null;
  kind: "DERIVED";
}

export interface OccurrenceProps {
  type: "ALAGAMENTO" | "INUNDACAO";
  occurred_on: string;
  subprefecture: string | null;
  kind: "OBSERVED";
}

export interface PolygonFeature<P> {
  type: "Feature";
  id?: number;
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: unknown };
  properties: P;
}

export interface RiskLayer {
  type: "FeatureCollection";
  features: PolygonFeature<RiskLayerProps>[];
  attribution?: string;
  disclaimer?: string;
}
