import { apiGet } from "@/lib/api-client";
import type { ForecastResponse } from "./types";

export async function fetchForecast(
  lat: number,
  lon: number,
  signal?: AbortSignal,
  fetchImpl?: typeof fetch,
): Promise<ForecastResponse> {
  const params = new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4) });
  const { data } = await apiGet<ForecastResponse>(`/api/v1/weather/forecast?${params}`, {
    signal,
    fetchImpl,
  });
  return data;
}

export interface NearbyStation {
  id: number;
  code: string;
  name: string;
  status: string;
  latitude: number;
  longitude: number;
  distance_km: number;
}

export async function fetchNearbyStations(
  lat: number,
  lon: number,
  signal?: AbortSignal,
  fetchImpl?: typeof fetch,
): Promise<NearbyStation[]> {
  const params = new URLSearchParams({
    lat: lat.toFixed(4),
    lon: lon.toFixed(4),
    radius_km: "30",
  });
  const { data } = await apiGet<{ items: NearbyStation[] }>(`/api/v1/stations/nearby?${params}`, {
    signal,
    fetchImpl,
  });
  return data.items;
}
