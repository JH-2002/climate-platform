"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchBasin, fetchBasinLayer, fetchBasins, fetchDemStatus, fetchProfile, fetchReservoirLayer, fetchSectorTerrain } from "./api";
import type { BasinSort } from "./types";

const HOUR = 60 * 60_000;
const noRetryOn = (codes: number[]) => (count: number, error: Error) =>
  count < 1 && !("status" in error && codes.includes(error.status as number));

export function useDemStatus() {
  return useQuery({ queryKey: ["geo", "dem"], queryFn: ({ signal }) => fetchDemStatus(signal), staleTime: HOUR });
}

export function useBasins(sort: BasinSort) {
  return useQuery({
    queryKey: ["geo", "basins", sort],
    queryFn: ({ signal }) => fetchBasins(sort, signal),
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useBasin(id: number | null) {
  return useQuery({
    queryKey: ["geo", "basin", id],
    queryFn: ({ signal }) => fetchBasin(id as number, signal),
    enabled: id !== null,
    staleTime: 10 * 60_000,
    retry: noRetryOn([404]),
  });
}

export function useSectorTerrain(sectorId: number | null) {
  return useQuery({
    queryKey: ["geo", "sector", sectorId],
    queryFn: ({ signal }) => fetchSectorTerrain(sectorId as number, signal),
    enabled: sectorId !== null,
    staleTime: HOUR,
    retry: noRetryOn([404]),
  });
}

export function useProfile(points: [number, number][]) {
  return useQuery({
    queryKey: ["geo", "profile", points],
    queryFn: ({ signal }) => fetchProfile(points, signal),
    enabled: points.length >= 2,
    staleTime: HOUR,
    retry: noRetryOn([422, 503]),
  });
}

export function useGeoLayers() {
  const basins = useQuery({ queryKey: ["geo", "layer", "basins"], queryFn: ({ signal }) => fetchBasinLayer(signal), staleTime: 10 * 60_000 });
  const reservoirs = useQuery({
    queryKey: ["geo", "layer", "reservoirs"],
    queryFn: ({ signal }) => fetchReservoirLayer(signal),
    staleTime: HOUR,
  });
  return { basins, reservoirs };
}
