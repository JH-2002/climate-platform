/** Estado da página /geo-3d na URL: aba, bacia escolhida, ordenação e pontos do perfil. */

import type { BasinSort } from "./types";

export type GeoTab = "bacias" | "perfil";

export interface GeoState {
  tab: GeoTab;
  basinId: number | null;
  sort: BasinSort;
  profile: [number, number][];
}

const SORTS: readonly BasinSort[] = ["alto", "setores", "ocorrencias", "piscinoes", "nome"];
export const SORT_LABELS: Record<BasinSort, string> = {
  alto: "Setores em alto ou crítico agora",
  setores: "Número de setores de risco",
  ocorrencias: "Ocorrências em 12 meses",
  piscinoes: "Volume dos piscinões",
  nome: "Nome",
};
export const MAX_PROFILE_POINTS = 10;

export function parsePoints(raw: string | null): [number, number][] {
  if (!raw) return [];
  const points: [number, number][] = [];
  for (const part of raw.split(";")) {
    const values = part.split(",").map(Number);
    if (values.length !== 2) continue;
    const [lon, lat] = values as [number, number];
    if (Number.isFinite(lon) && Number.isFinite(lat) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
      points.push([lon, lat]);
    }
  }
  return points.slice(0, MAX_PROFILE_POINTS);
}

export function parseGeoState(params: URLSearchParams): GeoState {
  const sort = params.get("ordem");
  const basin = Number(params.get("bacia"));
  return {
    tab: params.get("aba") === "perfil" ? "perfil" : "bacias",
    basinId: Number.isInteger(basin) && basin > 0 ? basin : null,
    sort: SORTS.includes(sort as BasinSort) ? (sort as BasinSort) : "alto",
    profile: parsePoints(params.get("perfil")),
  };
}

export function serializeGeoState(state: GeoState): string {
  const params = new URLSearchParams();
  params.set("aba", state.tab);
  if (state.basinId !== null) params.set("bacia", String(state.basinId));
  if (state.sort !== "alto") params.set("ordem", state.sort);
  if (state.profile.length > 0)
    params.set("perfil", state.profile.map(([lon, lat]) => `${lon.toFixed(5)},${lat.toFixed(5)}`).join(";"));
  return params.toString();
}

/** Perfis prontos: atravessam vales conhecidos e funcionam sem o mapa (NFR-124). */
export const PROFILE_EXAMPLES: { label: string; points: [number, number][] }[] = [
  { label: "Travessia do Rio Tietê na Penha", points: [[-46.55, -23.535], [-46.55, -23.495]] },
  { label: "Do Rio Pinheiros à Avenida Paulista", points: [[-46.695, -23.575], [-46.656, -23.5615]] },
  { label: "Vale do Aricanduva", points: [[-46.53, -23.578], [-46.5, -23.54]] },
];
