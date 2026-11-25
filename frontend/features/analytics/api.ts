import { apiBaseUrl, apiGet } from "@/lib/api-client";
import { assetUrl, demoEnabled } from "@/lib/demo";
import type {
  ClimatologyResponse,
  DatasetInfo,
  DescribeResult,
  DistributionResponse,
  InsightsResponse,
  KpisResponse,
  RankingResponse,
  RiskHistoryResponse,
  SeriesResponse,
  SourceHealth,
  TrendsResponse,
} from "./types";
import type { StudioState } from "./studio";

const BASE = "/api/v1/analytics";

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await apiGet<T>(`${BASE}${path}`, { signal })).data;
}

export const fetchKpis = (signal?: AbortSignal) => get<KpisResponse>("/kpis", signal);
export const fetchInsights = (signal?: AbortSignal) => get<InsightsResponse>("/insights", signal);
export const fetchDatasets = (signal?: AbortSignal) => get<DatasetInfo[]>("/datasets", signal);
export const fetchTrends = (signal?: AbortSignal) => get<TrendsResponse>("/trends", signal);
export const fetchRiskHistory = (signal?: AbortSignal) => get<RiskHistoryResponse>("/risk-history?days=7", signal);
export const fetchSourcesHealth = (signal?: AbortSignal) => get<SourceHealth[]>("/sources-health", signal);

export interface SeriesParams {
  dataset: string;
  variable: string;
  start: string;
  end: string;
  grain: string;
  agg: string;
  location?: string | null;
  compare?: string | null;
}

export function seriesQuery(params: SeriesParams): string {
  const query = new URLSearchParams({
    dataset: params.dataset,
    variable: params.variable,
    start: params.start,
    end: params.end,
    grain: params.grain,
    agg: params.agg,
  });
  if (params.location) query.set("location", params.location);
  if (params.compare) query.set("compare", params.compare);
  return query.toString();
}

export const fetchSeries = (params: SeriesParams, signal?: AbortSignal) =>
  get<SeriesResponse>(`/series?${seriesQuery(params)}`, signal);

/** Link de download do CSV (mesma consulta do gráfico, AC-087). */
export function seriesCsvUrl(params: SeriesParams): string {
  return demoEnabled()
    ? assetUrl(`${BASE}/series.csv?${seriesQuery(params)}`)
    : `${apiBaseUrl()}${BASE}/series.csv?${seriesQuery(params)}`;
}

export function studioSeriesParams(state: StudioState): SeriesParams {
  return {
    dataset: state.dataset,
    variable: state.variable,
    start: state.start,
    end: state.end,
    grain: state.grain,
    agg: state.agg,
    location: state.location,
    compare: state.compare,
  };
}

export const fetchClimatology = (dataset: string, variable: string, location: string | null, signal?: AbortSignal) => {
  const query = new URLSearchParams({ dataset, variable });
  if (location) query.set("location", location);
  return get<ClimatologyResponse>(`/climatology?${query}`, signal);
};

export const fetchDistribution = (location: string, start: string, end: string, signal?: AbortSignal) =>
  get<DistributionResponse>(`/distribution?${new URLSearchParams({ location, start, end })}`, signal);

export const fetchRanking = (dataset: string, variable: string, agg: string, start: string, end: string, signal?: AbortSignal) =>
  get<RankingResponse>(`/ranking?${new URLSearchParams({ dataset, variable, agg, start, end })}`, signal);

export const fetchDescribe = (
  dataset: string,
  variable: string,
  location: string | null,
  start: string,
  end: string,
  signal?: AbortSignal,
) => {
  const query = new URLSearchParams({ variable, start, end });
  if (location) query.set("location", location);
  return get<DescribeResult>(`/datasets/${dataset}/describe?${query}`, signal);
};
