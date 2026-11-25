"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchForecast, fetchNearbyStations } from "./api";

export function useForecast(lat: number, lon: number) {
  return useQuery({
    queryKey: ["weather", "forecast", lat.toFixed(4), lon.toFixed(4)],
    queryFn: ({ signal }) => fetchForecast(lat, lon, signal),
    refetchInterval: 10 * 60_000,
    retry: (count, error) => count < 1 && !("status" in error && error.status === 404),
  });
}

export function useNearbyStations(lat: number, lon: number) {
  return useQuery({
    queryKey: ["stations", "nearby", lat.toFixed(4), lon.toFixed(4)],
    queryFn: ({ signal }) => fetchNearbyStations(lat, lon, signal),
    staleTime: 60 * 60_000,
  });
}
