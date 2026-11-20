/** Respostas de `/api/v1/analytics/*` (spec 006). */

export type DataKind = "OBSERVED" | "MODELED" | "FORECAST" | "DERIVED";

export interface Kpi {
  code: string;
  label: string;
  value: number | null;
  unit: string;
  detail: string | null;
  period_start: string | null;
  period_end: string | null;
  kind: DataKind;
  source: string;
  freshness: string | null;
  href: string;
  available: boolean;
}

export interface KpisResponse {
  generated_at: string;
  items: Kpi[];
}

export interface InsightMetric {
  name: string;
  value: number | string | null;
  unit: string;
  kind: string;
  source: string;
}

export interface Insight {
  code: string;
  severity: "info" | "atencao";
  text: string;
  metrics: InsightMetric[];
  sources: string[];
  rules_version: string;
}

export interface InsightsResponse {
  generated_at: string;
  rules_version: string;
  items: Insight[];
  notes: string[];
}
