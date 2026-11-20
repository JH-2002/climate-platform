import { apiGet } from "@/lib/api-client";
import type { FeatureCollection } from "@/features/map/types";
import type {
  NearestRiskArea,
  OccurrenceProps,
  RiskAreaDetail,
  RiskAreaPage,
  RiskLayer,
  RiskSummary,
} from "./types";
import type { RiskFilters } from "./state";

export async function fetchRiskSummary(signal?: AbortSignal): Promise<RiskSummary> {
  return (await apiGet<RiskSummary>("/api/v1/risk/summary", { signal })).data;
}

export function riskAreasQuery(filters: RiskFilters, limit = 200): string {
  const params = new URLSearchParams({ limit: String(limit) });
  if (filters.category) params.set("category", filters.category);
  if (filters.subprefecture) params.set("subprefecture", filters.subprefecture);
  return `/api/v1/risk/areas?${params}`;
}

export async function fetchRiskAreas(filters: RiskFilters, signal?: AbortSignal): Promise<RiskAreaPage> {
  return (await apiGet<RiskAreaPage>(riskAreasQuery(filters), { signal })).data;
}

export async function fetchRiskArea(id: number, signal?: AbortSignal): Promise<RiskAreaDetail> {
  return (await apiGet<RiskAreaDetail>(`/api/v1/risk/areas/${id}`, { signal })).data;
}

export async function fetchNearestRisk(lat: number, lon: number, signal?: AbortSignal): Promise<NearestRiskArea> {
  const params = new URLSearchParams({ lat: lat.toFixed(5), lon: lon.toFixed(5) });
  return (await apiGet<NearestRiskArea>(`/api/v1/risk/nearest?${params}`, { signal })).data;
}

export async function fetchRiskLayer(signal?: AbortSignal): Promise<RiskLayer> {
  return (await apiGet<RiskLayer>("/api/v1/map/layers/risk", { signal })).data;
}

export async function fetchOccurrencesLayer(signal?: AbortSignal): Promise<FeatureCollection<OccurrenceProps>> {
  return (
    await apiGet<FeatureCollection<OccurrenceProps>>("/api/v1/map/layers/flood-occurrences", { signal })
  ).data;
}
