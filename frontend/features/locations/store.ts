/**
 * Locais salvos neste navegador (ADR-008). Funções puras sobre um armazenamento injetável,
 * com tolerância a falhas do localStorage (modo privado, cota, conteúdo corrompido).
 */

export interface SavedLocation {
  id: string;
  name: string;
  lat: number;
  lon: number;
}

export interface LocationsState {
  locations: SavedLocation[];
  defaultId: string;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const STORAGE_KEY = "climate-platform:locais:v1";

export const PRESET_LOCATION: SavedLocation = {
  id: "centro-sp",
  name: "Centro de São Paulo",
  lat: -23.5505,
  lon: -46.6333,
};

export const INITIAL_STATE: LocationsState = {
  locations: [PRESET_LOCATION],
  defaultId: PRESET_LOCATION.id,
};

function isValidCoordinate(lat: number, lon: number): boolean {
  return (
    Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180
  );
}

function isSavedLocation(value: unknown): value is SavedLocation {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.name === "string" &&
    typeof v.lat === "number" &&
    typeof v.lon === "number" &&
    isValidCoordinate(v.lat, v.lon)
  );
}

/** Retorna a mensagem de erro, ou null se o local for válido. */
export function validateLocation(name: string, lat: number, lon: number): string | null {
  if (!name.trim()) return "Informe um nome para o local.";
  if (name.trim().length > 60) return "Use um nome com até 60 caracteres.";
  if (!isValidCoordinate(lat, lon)) {
    return "Coordenadas inválidas: latitude entre -90 e 90, longitude entre -180 e 180.";
  }
  return null;
}

export function loadLocations(storage: StorageLike | null): LocationsState {
  if (!storage) return INITIAL_STATE;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return INITIAL_STATE;
    const parsed = JSON.parse(raw) as { locations?: unknown; defaultId?: unknown };
    const saved = Array.isArray(parsed.locations) ? parsed.locations.filter(isSavedLocation) : [];
    const locations = [PRESET_LOCATION, ...saved.filter((l) => l.id !== PRESET_LOCATION.id)];
    const defaultId =
      typeof parsed.defaultId === "string" && locations.some((l) => l.id === parsed.defaultId)
        ? parsed.defaultId
        : PRESET_LOCATION.id;
    return { locations, defaultId };
  } catch {
    return INITIAL_STATE;
  }
}

/** Grava o estado; devolve false se o navegador recusar (o estado em memória continua valendo). */
export function saveLocations(storage: StorageLike | null, state: LocationsState): boolean {
  if (!storage) return false;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function addLocation(
  state: LocationsState,
  location: Omit<SavedLocation, "id">,
  makeId: () => string = () => `local-${Date.now().toString(36)}`,
): LocationsState {
  const entry: SavedLocation = {
    id: makeId(),
    name: location.name.trim(),
    lat: Number(location.lat.toFixed(5)),
    lon: Number(location.lon.toFixed(5)),
  };
  return { ...state, locations: [...state.locations, entry] };
}

export function removeLocation(state: LocationsState, id: string): LocationsState {
  if (id === PRESET_LOCATION.id) return state;
  const locations = state.locations.filter((l) => l.id !== id);
  const defaultId = state.defaultId === id ? PRESET_LOCATION.id : state.defaultId;
  return { locations, defaultId };
}

export function setDefaultLocation(state: LocationsState, id: string): LocationsState {
  return state.locations.some((l) => l.id === id) ? { ...state, defaultId: id } : state;
}
