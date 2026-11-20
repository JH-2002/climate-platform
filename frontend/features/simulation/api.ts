import { apiGet, apiPost } from "@/lib/api-client";
import type { FeatureCollection } from "@/features/map/types";
import type {
  Center,
  Preset,
  RunListItem,
  SimulatedSector,
  SimulatedSectorPage,
  SimulationLayerProps,
  SimulationRun,
} from "./types";

export async function fetchPresets(signal?: AbortSignal): Promise<Preset[]> {
  return (await apiGet<Preset[]>("/api/v1/simulation/presets", { signal })).data;
}

export async function fetchCenters(signal?: AbortSignal): Promise<Center[]> {
  return (await apiGet<Center[]>("/api/v1/simulation/centers", { signal })).data;
}

export async function createSimulation(body: Record<string, unknown>): Promise<SimulationRun> {
  return (await apiPost<SimulationRun>("/api/v1/simulation/runs", body)).data;
}

export async function fetchRecentRuns(signal?: AbortSignal): Promise<RunListItem[]> {
  return (await apiGet<RunListItem[]>("/api/v1/simulation/runs?limit=10", { signal })).data;
}

export async function fetchSimulation(id: string, signal?: AbortSignal): Promise<SimulationRun> {
  return (await apiGet<SimulationRun>(`/api/v1/simulation/runs/${id}`, { signal })).data;
}

export function simulatedSectorsQuery(id: string, limit = 1000): string {
  return `/api/v1/simulation/runs/${id}/sectors?limit=${limit}`;
}

export async function fetchSimulatedSectors(id: string, signal?: AbortSignal): Promise<SimulatedSectorPage> {
  return (await apiGet<SimulatedSectorPage>(simulatedSectorsQuery(id), { signal })).data;
}

export async function fetchSimulatedSector(id: string, sectorId: number, signal?: AbortSignal): Promise<SimulatedSector> {
  return (await apiGet<SimulatedSector>(`/api/v1/simulation/runs/${id}/sectors/${sectorId}`, { signal })).data;
}

export async function fetchSimulationLayer(
  id: string,
  signal?: AbortSignal,
): Promise<FeatureCollection<SimulationLayerProps>> {
  return (await apiGet<FeatureCollection<SimulationLayerProps>>(`/api/v1/map/layers/simulation/${id}`, { signal })).data;
}
