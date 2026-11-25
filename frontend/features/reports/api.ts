import { apiGet, apiPost } from "@/lib/api-client";
import type { ReportFormat, ReportRequest, ReportType, ReportTypeInfo } from "./types";

export async function fetchReportTypes(signal?: AbortSignal): Promise<ReportTypeInfo[]> {
  return (await apiGet<ReportTypeInfo[]>("/api/v1/reports/types", { signal })).data;
}

export async function fetchReports(ids: string[], signal?: AbortSignal): Promise<ReportRequest[]> {
  if (ids.length === 0) return [];
  const params = new URLSearchParams({ ids: ids.join(",") });
  return (await apiGet<ReportRequest[]>(`/api/v1/reports?${params}`, { signal })).data;
}

export async function createReport(
  type: ReportType,
  format: ReportFormat,
  params: Record<string, unknown>,
): Promise<ReportRequest> {
  return (await apiPost<ReportRequest>("/api/v1/reports", { type, format, params })).data;
}
