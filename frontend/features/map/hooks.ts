"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchForecastPointsLayer, fetchRegion, fetchStationsLayer } from "./api";

export function useMapLayers() {
  const region = useQuery({ queryKey: ["map", "region"], queryFn: ({ signal }) => fetchRegion(signal), staleTime: Infinity });
  const stations = useQuery({
    queryKey: ["map", "stations"],
    queryFn: ({ signal }) => fetchStationsLayer(signal),
    staleTime: 30 * 60_000,
  });
  const forecast = useQuery({
    queryKey: ["map", "forecast-points"],
    queryFn: ({ signal }) => fetchForecastPointsLayer(signal),
    refetchInterval: 10 * 60_000,
  });
  return { region, stations, forecast };
}
