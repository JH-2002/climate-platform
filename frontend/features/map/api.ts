import { apiGet } from "@/lib/api-client";
import type { FeatureCollection, ForecastPointProps, RegionFeature, StationProps } from "./types";

export async function fetchRegion(signal?: AbortSignal): Promise<RegionFeature> {
  return (await apiGet<RegionFeature>("/api/v1/map/region", { signal })).data;
}

export async function fetchStationsLayer(signal?: AbortSignal): Promise<FeatureCollection<StationProps>> {
  return (await apiGet<FeatureCollection<StationProps>>("/api/v1/map/layers/stations", { signal })).data;
}

export async function fetchForecastPointsLayer(
  signal?: AbortSignal,
): Promise<FeatureCollection<ForecastPointProps>> {
  return (
    await apiGet<FeatureCollection<ForecastPointProps>>("/api/v1/map/layers/forecast-points", { signal })
  ).data;
}
