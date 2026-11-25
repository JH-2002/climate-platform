import { apiGet } from "@/lib/api-client";
import type { FeatureCollection } from "@/features/map/types";
import type {
  BasinBlock,
  BasinDetail,
  BasinLayerProps,
  BasinList,
  BasinSort,
  DemStatus,
  Profile,
  SectorTerrain,
} from "./types";

export async function fetchDemStatus(signal?: AbortSignal): Promise<DemStatus> {
  return (await apiGet<DemStatus>("/api/v1/geo/dem", { signal })).data;
}

export async function fetchBasins(sort: BasinSort, signal?: AbortSignal): Promise<BasinList> {
  return (await apiGet<BasinList>(`/api/v1/geo/basins?ordem=${sort}`, { signal })).data;
}

export async function fetchBasin(id: number, signal?: AbortSignal): Promise<BasinDetail> {
  return (await apiGet<BasinDetail>(`/api/v1/geo/basins/${id}`, { signal })).data;
}

export async function fetchSectorTerrain(sectorId: number, signal?: AbortSignal): Promise<SectorTerrain> {
  return (await apiGet<SectorTerrain>(`/api/v1/geo/sectors/${sectorId}/terrain`, { signal })).data;
}

/** "lon,lat;lon,lat" com 5 casas (~1 m), como a API espera. */
export function profileQuery(points: [number, number][]): string {
  return points.map(([lon, lat]) => `${lon.toFixed(5)},${lat.toFixed(5)}`).join(";");
}

export async function fetchProfile(points: [number, number][], signal?: AbortSignal): Promise<Profile> {
  return (await apiGet<Profile>(`/api/v1/geo/profile?pontos=${encodeURIComponent(profileQuery(points))}`, { signal }))
    .data;
}

export async function fetchBasinLayer(signal?: AbortSignal): Promise<FeatureCollection<BasinLayerProps>> {
  return (await apiGet<FeatureCollection<BasinLayerProps>>("/api/v1/map/layers/basins", { signal })).data;
}

export async function fetchReservoirLayer(signal?: AbortSignal): Promise<FeatureCollection<Record<string, unknown>>> {
  return (await apiGet<FeatureCollection<Record<string, unknown>>>("/api/v1/map/layers/reservoirs", { signal })).data;
}

export function drainageUrl(bbox: [number, number, number, number], zoom: number): string {
  return `/api/v1/map/layers/drainage?bbox=${bbox.map((v) => v.toFixed(4)).join(",")}&zoom=${Math.floor(zoom)}`;
}

function simulationQuery(simulationId: string | null): string {
  return simulationId ? `?simulacao=${simulationId}` : "";
}

export async function fetchBasinBlock(id: number, simulationId: string | null, signal?: AbortSignal): Promise<BasinBlock> {
  return (await apiGet<BasinBlock>(`/api/v1/geo/basins/${id}/block${simulationQuery(simulationId)}`, { signal })).data;
}

export function reliefUrl(id: number, simulationId: string | null): string {
  return `/api/v1/geo/basins/${id}/relief.png${simulationQuery(simulationId)}`;
}

/** URL absoluta dos blocos de relevo do Copernicus (o MapLibre exige URL completa). */
export function terrainTilesUrl(origin: string): string {
  return `${origin}/api/v1/geo/terrain/{z}/{x}/{y}.png`;
}
