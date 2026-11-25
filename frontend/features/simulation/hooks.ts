"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSimulation,
  fetchCenters,
  fetchPresets,
  fetchRecentRuns,
  fetchSimulatedSector,
  fetchSimulatedSectors,
  fetchSimulation,
  fetchSimulationLayer,
} from "./api";

const notFound = (count: number, error: Error) => count < 1 && !("status" in error && error.status === 404);

export function usePresets() {
  return useQuery({ queryKey: ["simulation", "presets"], queryFn: ({ signal }) => fetchPresets(signal), staleTime: Infinity });
}

export function useCenters() {
  return useQuery({
    queryKey: ["simulation", "centers"],
    queryFn: ({ signal }) => fetchCenters(signal),
    staleTime: 60 * 60_000,
  });
}

/** Uma simulação gravada não muda: sem recarga periódica. */
export function useSimulation(id: string | null) {
  return useQuery({
    queryKey: ["simulation", "run", id],
    queryFn: ({ signal }) => fetchSimulation(id as string, signal),
    enabled: id !== null,
    staleTime: Infinity,
    retry: notFound,
  });
}

export function useSimulatedSectors(id: string | null) {
  return useQuery({
    queryKey: ["simulation", "sectors", id],
    queryFn: ({ signal }) => fetchSimulatedSectors(id as string, signal),
    enabled: id !== null,
    staleTime: Infinity,
    retry: notFound,
  });
}

export function useSimulatedSector(id: string | null, sectorId: number | null) {
  return useQuery({
    queryKey: ["simulation", "sector", id, sectorId],
    queryFn: ({ signal }) => fetchSimulatedSector(id as string, sectorId as number, signal),
    enabled: id !== null && sectorId !== null,
    staleTime: Infinity,
    retry: notFound,
  });
}

export function useSimulationLayer(id: string | null) {
  return useQuery({
    queryKey: ["simulation", "layer", id],
    queryFn: ({ signal }) => fetchSimulationLayer(id as string, signal),
    enabled: id !== null,
    staleTime: Infinity,
    retry: notFound,
  });
}

export function useRecentRuns() {
  return useQuery({ queryKey: ["simulation", "recent"], queryFn: ({ signal }) => fetchRecentRuns(signal) });
}

export function useRunSimulation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => createSimulation(body),
    onSuccess: (run) => {
      client.setQueryData(["simulation", "run", run.id], run);
      void client.invalidateQueries({ queryKey: ["simulation", "recent"] });
    },
  });
}
