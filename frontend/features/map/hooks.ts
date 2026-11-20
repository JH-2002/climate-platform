"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOccurrencesLayer, fetchRiskLayer } from "@/features/risk/api";
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
  const risk = useQuery({
    queryKey: ["map", "risk"],
    queryFn: ({ signal }) => fetchRiskLayer(signal),
    refetchInterval: 10 * 60_000,
  });
  const occurrences = useQuery({
    queryKey: ["map", "occurrences"],
    queryFn: ({ signal }) => fetchOccurrencesLayer(signal),
    staleTime: 60 * 60_000,
  });
  return { region, stations, forecast, risk, occurrences };
}
