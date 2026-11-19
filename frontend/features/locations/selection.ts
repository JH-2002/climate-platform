import type { SavedLocation } from "./store";

export interface SelectedLocation {
  name: string;
  lat: number;
  lon: number;
}

interface ParamsLike {
  get(name: string): string | null;
}

/** Local selecionado: o da URL, se válido (FR-048); senão, o local padrão. */
export function resolveSelectedLocation(
  params: ParamsLike,
  locations: SavedLocation[],
  defaultId: string,
): SelectedLocation {
  const lat = Number(params.get("lat"));
  const lon = Number(params.get("lon"));
  const hasCoords =
    params.get("lat") !== null &&
    params.get("lon") !== null &&
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lon) <= 180;
  if (hasCoords) {
    const known = locations.find((l) => l.lat === lat && l.lon === lon);
    return { name: params.get("nome") || known?.name || "Local da URL", lat, lon };
  }
  const fallback = locations.find((l) => l.id === defaultId) ?? locations[0];
  return fallback
    ? { name: fallback.name, lat: fallback.lat, lon: fallback.lon }
    : { name: "Centro de São Paulo", lat: -23.5505, lon: -46.6333 };
}
