/** Modo (2D/3D) e camadas do mapa, sincronizados com a URL (FR-059). Funções puras. */

export type MapMode = "2d" | "3d";
export type LayerId = "estacoes" | "chuva" | "risco" | "ocorrencias" | "locais" | "regiao";

export const ALL_LAYERS: readonly LayerId[] = [
  "estacoes",
  "chuva",
  "risco",
  "ocorrencias",
  "locais",
  "regiao",
];

export const LAYER_LABELS: Record<LayerId, string> = {
  estacoes: "Estações do INMET",
  chuva: "Chuva prevista (24 h)",
  risco: "Risco estimado (setores)",
  ocorrencias: "Ocorrências registradas",
  locais: "Meus locais",
  regiao: "Região de interesse",
};

export interface MapState {
  mode: MapMode;
  layers: LayerId[];
}

export const DEFAULT_STATE: MapState = { mode: "3d", layers: [...ALL_LAYERS] };

interface ParamsLike {
  get(name: string): string | null;
}

function isLayer(value: string): value is LayerId {
  return (ALL_LAYERS as readonly string[]).includes(value);
}

export function parseMapState(params: ParamsLike): MapState {
  const modeParam = params.get("modo");
  const mode: MapMode = modeParam === "2d" || modeParam === "3d" ? modeParam : DEFAULT_STATE.mode;
  const layersParam = params.get("camadas");
  if (layersParam === null) return { mode, layers: [...DEFAULT_STATE.layers] };
  const layers = ALL_LAYERS.filter((id) => layersParam.split(",").map((s) => s.trim()).filter(isLayer).includes(id));
  return { mode, layers };
}

export function serializeMapState(state: MapState): string {
  const params = new URLSearchParams({ modo: state.mode, camadas: state.layers.join(",") });
  return params.toString();
}

export function toggleLayer(state: MapState, id: LayerId): MapState {
  const layers = state.layers.includes(id)
    ? state.layers.filter((l) => l !== id)
    : ALL_LAYERS.filter((l) => l === id || state.layers.includes(l));
  return { ...state, layers };
}
