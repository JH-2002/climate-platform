"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchNearestRisk, fetchRiskArea, fetchRiskAreas, fetchRiskSummary } from "./api";
import type { RiskFilters } from "./state";

const REFRESH_MS = 10 * 60_000;

export function useRiskSummary() {
  return useQuery({
    queryKey: ["risk", "summary"],
    queryFn: ({ signal }) => fetchRiskSummary(signal),
    refetchInterval: REFRESH_MS,
  });
}

export function useRiskAreas(filters: RiskFilters) {
  return useQuery({
    queryKey: ["risk", "areas", filters.category, filters.subprefecture],
    queryFn: ({ signal }) => fetchRiskAreas(filters, signal),
    refetchInterval: REFRESH_MS,
  });
}

export function useRiskArea(id: number | null) {
  return useQuery({
    queryKey: ["risk", "area", id],
    queryFn: ({ signal }) => fetchRiskArea(id as number, signal),
    enabled: id !== null,
    retry: (count, error) => count < 1 && !("status" in error && error.status === 404),
  });
}

export function useNearestRisk(lat: number, lon: number) {
  return useQuery({
    queryKey: ["risk", "nearest", lat.toFixed(4), lon.toFixed(4)],
    queryFn: ({ signal }) => fetchNearestRisk(lat, lon, signal),
    refetchInterval: REFRESH_MS,
  });
}
