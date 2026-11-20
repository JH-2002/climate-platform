import { apiGet } from "@/lib/api-client";
import type { InsightsResponse, KpisResponse } from "./types";

export async function fetchKpis(signal?: AbortSignal): Promise<KpisResponse> {
  return (await apiGet<KpisResponse>("/api/v1/analytics/kpis", { signal })).data;
}

export async function fetchInsights(signal?: AbortSignal): Promise<InsightsResponse> {
  return (await apiGet<InsightsResponse>("/api/v1/analytics/insights", { signal })).data;
}
