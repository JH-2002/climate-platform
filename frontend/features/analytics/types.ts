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

export interface VariableInfo {
  code: string;
  label: string;
  unit: string;
  aggregations: string[];
}

export interface LocationInfo {
  key: string;
  label: string;
  latitude: number | null;
  longitude: number | null;
  detail: string | null;
}

export interface DatasetInfo {
  id: string;
  name: string;
  description: string;
  kind: DataKind;
  resolution: string;
  spatial: string;
  source_code: string;
  source_name: string | null;
  attribution: string | null;
  license: string | null;
  freshness: string | null;
  variables: VariableInfo[];
  grains: string[];
  visualizations: string[];
  numeric: boolean;
  caveats: string[];
  records: number;
  period_start: string | null;
  period_end: string | null;
  locations: LocationInfo[];
}

export interface DescribeResult {
  dataset: string;
  variable: string;
  unit: string;
  kind: string;
  location: string | null;
  start: string;
  end: string;
  expected: number;
  n: number;
  missing: number;
  coverage: number;
  mean: number | null;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
  std: number | null;
  p5: number | null;
  p25: number | null;
  p75: number | null;
  p95: number | null;
  outlier_count: number;
  outliers: number[];
  method: string;
}

export interface SeriesPoint {
  start: string;
  value: number | null;
  n: number;
  expected: number;
  coverage: number;
  partial: boolean;
  insufficient: boolean;
  reference: number | null;
}

export interface SeriesResponse {
  dataset: string;
  dataset_name: string;
  variable: string;
  variable_label: string;
  unit: string;
  kind: DataKind;
  location: string | null;
  grain: string;
  agg: string;
  start: string;
  end: string;
  compare: string | null;
  reference_label: string | null;
  reference_kind: string | null;
  points: SeriesPoint[];
  source: string | null;
  attribution: string | null;
  caveats: string[];
}

export interface MonthClimate {
  month: number;
  mean: number | null;
  p10: number | null;
  p25: number | null;
  p75: number | null;
  p90: number | null;
  years_used: number;
}

export interface ClimatologyResponse {
  dataset: string;
  variable: string;
  unit: string;
  kind: DataKind;
  location: string | null;
  period: string;
  months: MonthClimate[];
  annual_mean: number | null;
  published: number[] | null;
  published_annual: number | null;
}

export interface DistributionResponse {
  location: string;
  start: string;
  end: string;
  days: number;
  wet_days: number;
  threshold: number;
  bins: { low: number; high: number; count: number }[];
  extremes: { day: string; value: number }[];
}

export interface RankingResponse {
  dataset: string;
  variable: string;
  unit: string;
  kind: DataKind;
  agg: string;
  start: string;
  end: string;
  items: { key: string; value: number; n: number }[];
}

export interface YearValue {
  year: number;
  value: number;
}

export interface TrendsResponse {
  station: string;
  unit: string;
  kind: DataKind;
  annual: YearValue[];
  moving_average_10y: YearValue[];
  normals: { period: string; computed: number; published: number | null; difference: number | null }[];
  wettest: YearValue[];
  driest: YearValue[];
  note: string;
  attribution: string | null;
}

export interface RiskHistoryResponse {
  runs: { computed_at: string; counts: Record<string, number> }[];
  by_subprefecture: { name: string; counts: Record<string, number>; total: number }[];
  by_basin: { name: string; counts: Record<string, number>; total: number }[];
  engine_note: string;
}

export interface SourceHealth {
  code: string;
  name: string;
  freshness: string;
  reason: string;
  last_success_at: string | null;
  age_hours: number | null;
  expected_interval_h: number;
  runs_7d: number;
  success_7d: number;
  availability_7d: number | null;
  runs_30d: number;
  success_30d: number;
  availability_30d: number | null;
  mean_duration_s: number | null;
  rejected_rate: number | null;
  last_failure_at: string | null;
  last_failure: string | null;
  coverage: string | null;
}
