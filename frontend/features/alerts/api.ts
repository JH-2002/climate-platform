import type { FeatureCollection } from "@/features/map/types";
import { apiGet } from "@/lib/api-client";
import type { ActiveAlerts, AlertCategory, AlertHistory, AlertLayerProps, OfficialAlert, OfficialAlertDetail } from "./types";

export async function fetchActiveAlerts(signal?: AbortSignal): Promise<ActiveAlerts> {
  return (await apiGet<ActiveAlerts>("/api/v1/alerts/active", { signal })).data;
}

export function historyQuery(category: AlertCategory | null, page = 1): string {
  const params = new URLSearchParams({ pagina: String(page) });
  if (category) params.set("categoria", category);
  return `/api/v1/alerts?${params}`;
}

export async function fetchAlertHistory(
  category: AlertCategory | null,
  page: number,
  signal?: AbortSignal,
): Promise<AlertHistory> {
  return (await apiGet<AlertHistory>(historyQuery(category, page), { signal })).data;
}

export async function fetchOfficialAlert(id: number, signal?: AbortSignal): Promise<OfficialAlertDetail> {
  return (await apiGet<OfficialAlertDetail>(`/api/v1/alerts/official/${id}`, { signal })).data;
}

export async function fetchAlertsAt(lat: number, lon: number, signal?: AbortSignal): Promise<OfficialAlert[]> {
  const params = new URLSearchParams({ lat: lat.toFixed(5), lon: lon.toFixed(5) });
  return (await apiGet<OfficialAlert[]>(`/api/v1/alerts/at?${params}`, { signal })).data;
}

export async function fetchAlertsLayer(signal?: AbortSignal): Promise<FeatureCollection<AlertLayerProps>> {
  return (await apiGet<FeatureCollection<AlertLayerProps>>("/api/v1/map/layers/alerts", { signal })).data;
}
