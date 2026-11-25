"use client";

/**
 * Mapa da geointeligência (FR-126). Carregado só nesta página (import dinâmico).
 * Bacias coloridas pelos setores em alto ou crítico agora; drenagem carregada pela área visível
 * (NFR-123); piscinões; linha do perfil. Relevo 3D visual: Terrain Tiles (ADR-009); os cálculos
 * usam o Copernicus no backend (ADR-013).
 */

import "maplibre-gl/dist/maplibre-gl.css";
import { basePath } from "@/lib/demo";
import type { GeoJSON as GeoJSONData } from "geojson";
import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { drainageUrl } from "@/features/geo/api";
import type { BasinLayerProps } from "@/features/geo/types";
import type { FeatureCollection } from "@/features/map/types";
import { apiGet } from "@/lib/api-client";
import { DEFAULT_MAP_STYLE_URL, DEFAULT_TERRAIN_TILES_URL } from "@/lib/map-sources.mjs";

const STYLE_URL = process.env.NEXT_PUBLIC_MAP_STYLE_URL || DEFAULT_MAP_STYLE_URL;
const WORKER_URL = process.env.NEXT_PUBLIC_MAPLIBRE_WORKER_URL ?? `${basePath()}/vendor/maplibre-gl-worker.mjs`;
const TERRAIN_URL =
  process.env.NEXT_PUBLIC_TERRAIN_TILES_URL || DEFAULT_TERRAIN_TILES_URL;
const ATTRIBUTION =
  "Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo · Relevo do mapa: Terrain Tiles (Mapzen/AWS)";
const SAO_PAULO: [number, number] = [-46.6333, -23.62];
const EMPTY = { type: "FeatureCollection", features: [] } as unknown as GeoJSONData;
// Mesma escala do ranking: 0, 1–2, 3–9, 10+ setores em alto ou crítico.
const BASIN_FILL = ["step", ["get", "high_or_above_now"], "#dbe7ef", 1, "#f6c38b", 3, "#e8803a", 10, "#b3261e"];

export type GeoMapMode = "bacias" | "perfil";

interface Props {
  basins?: FeatureCollection<BasinLayerProps>;
  reservoirs?: FeatureCollection<Record<string, unknown>>;
  selectedBasinId: number | null;
  mode: GeoMapMode;
  profile: [number, number][];
  onSelectBasin: (id: number) => void;
  onAddPoint: (lon: number, lat: number) => void;
}

function setData(map: MapLibreMap, id: string, data: unknown) {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as GeoJSONData);
}

function profileCollection(points: [number, number][]): unknown {
  return {
    type: "FeatureCollection",
    features: [
      ...(points.length >= 2
        ? [{ type: "Feature", properties: { kind: "line" }, geometry: { type: "LineString", coordinates: points } }]
        : []),
      ...points.map((p, i) => ({
        type: "Feature",
        properties: { kind: "point", label: String(i + 1) },
        geometry: { type: "Point", coordinates: p },
      })),
    ],
  };
}

export default function GeoMap(props: Props) {
  const { basins, reservoirs, selectedBasinId, mode, profile } = props;
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const handlers = useRef({ props });
  handlers.current = { props };
  const [ready, setReady] = useState(false);
  const [is3d, setIs3d] = useState(false);
  const [drainageNote, setDrainageNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    let controller: AbortController | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function loadDrainage() {
      if (!map) return;
      const b = map.getBounds();
      controller?.abort();
      controller = new AbortController();
      try {
        const { data } = await apiGet<FeatureCollection<Record<string, unknown>> & { truncated?: boolean }>(
          drainageUrl([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], map.getZoom()),
          { signal: controller.signal },
        );
        if (!map) return;
        setData(map, "drenagem", data);
        setDrainageNote(
          map.getZoom() < 12
            ? "Rios e córregos a céu aberto. Aproxime para ver também os canalizados subterrâneos."
            : data.truncated
              ? "Muitos trechos nesta área: aproxime para ver todos."
              : null,
        );
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setDrainageNote("Drenagem indisponível agora.");
      }
    }

    void (async () => {
      const maplibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      maplibre.setWorkerUrl(WORKER_URL);
      map = new maplibre.Map({
        container: container.current,
        style: STYLE_URL,
        center: SAO_PAULO,
        zoom: 9.6,
        maxPitch: 75,
        attributionControl: { compact: false, customAttribution: ATTRIBUTION },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibre.ScaleControl({ unit: "metric" }), "bottom-left");
      map.on("load", () => {
        if (!map) return;
        map.addSource("terreno", { type: "raster-dem", tiles: [TERRAIN_URL], encoding: "terrarium", tileSize: 256, maxzoom: 15 });
        for (const id of ["bacias", "drenagem", "piscinoes", "perfil"]) map.addSource(id, { type: "geojson", data: EMPTY });
        map.addLayer({
          id: "bacias-preenchimento",
          type: "fill",
          source: "bacias",
          paint: { "fill-color": BASIN_FILL as never, "fill-opacity": 0.45 },
        });
        map.addLayer({
          id: "bacias-contorno",
          type: "line",
          source: "bacias",
          paint: { "line-color": "#4b5d6b", "line-width": 0.8 },
        });
        map.addLayer({
          id: "bacia-escolhida",
          type: "line",
          source: "bacias",
          filter: ["==", ["get", "id"], -1],
          paint: { "line-color": "#0b5c7a", "line-width": 3.5 },
        });
        map.addLayer({
          id: "drenagem-linhas",
          type: "line",
          source: "drenagem",
          paint: {
            "line-color": ["case", ["get", "open_channel"], "#1d6fd6", "#7b8fa6"],
            "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.8, 14, 2.2],
            "line-dasharray": ["case", ["get", "open_channel"], ["literal", [1, 0]], ["literal", [2, 2]]] as never,
          },
        });
        map.addLayer({
          id: "piscinoes-pontos",
          type: "circle",
          source: "piscinoes",
          paint: {
            "circle-radius": 5,
            "circle-color": "#0f766e",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1.5,
          },
        });
        map.addLayer({
          id: "perfil-linha",
          type: "line",
          source: "perfil",
          filter: ["==", ["get", "kind"], "line"],
          paint: { "line-color": "#111827", "line-width": 3 },
        });
        map.addLayer({
          id: "perfil-pontos",
          type: "circle",
          source: "perfil",
          filter: ["==", ["get", "kind"], "point"],
          paint: { "circle-radius": 7, "circle-color": "#111827", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 },
        });
        map.addLayer({
          id: "perfil-rotulos",
          type: "symbol",
          source: "perfil",
          filter: ["==", ["get", "kind"], "point"],
          layout: { "text-field": ["get", "label"], "text-size": 11, "text-allow-overlap": true },
          paint: { "text-color": "#ffffff" },
        });
        map.on("click", "bacias-preenchimento", (e: MapLayerMouseEvent) => {
          if (handlers.current.props.mode !== "bacias") return;
          const id = Number(e.features?.[0]?.properties?.id);
          if (Number.isFinite(id)) handlers.current.props.onSelectBasin(id);
        });
        map.on("click", (e: MapMouseEvent) => {
          if (handlers.current.props.mode === "perfil") handlers.current.props.onAddPoint(e.lngLat.lng, e.lngLat.lat);
        });
        map.on("moveend", () => {
          clearTimeout(timer);
          timer = setTimeout(() => void loadDrainage(), 250);
        });
        void loadDrainage();
        setReady(true);
      });
    })();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      controller?.abort();
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (ready && map && basins) setData(map, "bacias", basins);
  }, [ready, basins]);

  useEffect(() => {
    const map = mapRef.current;
    if (ready && map && reservoirs) setData(map, "piscinoes", reservoirs);
  }, [ready, reservoirs]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("bacia-escolhida", ["==", ["get", "id"], selectedBasinId ?? -1]);
    if (selectedBasinId === null || !basins) return;
    const feature = basins.features.find((f) => f.properties.id === selectedBasinId);
    if (!feature) return;
    const coords: number[][] = [];
    const walk = (c: unknown): void => {
      if (Array.isArray(c) && typeof c[0] === "number") coords.push(c as number[]);
      else if (Array.isArray(c)) c.forEach(walk);
    };
    walk((feature.geometry as { coordinates: unknown }).coordinates);
    if (coords.length === 0) return;
    const lons = coords.map((c) => c[0]!);
    const lats = coords.map((c) => c[1]!);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 32, duration: 0 },
    );
  }, [ready, selectedBasinId, basins]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "perfil", profileCollection(profile));
    map.getCanvas().style.cursor = mode === "perfil" ? "crosshair" : "";
  }, [ready, profile, mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setTerrain(is3d ? { source: "terreno", exaggeration: 1.5 } : null);
    map.easeTo({ pitch: is3d ? 60 : 0, bearing: is3d ? -20 : 0, duration: 0 });
  }, [ready, is3d]);

  return (
    <div className="space-y-1">
      <div className="relative">
        <div
          ref={container}
          className="h-[60vh] min-h-80 w-full overflow-hidden rounded-lg border border-surface-border"
          role="region"
          aria-label="Mapa de bacias, drenagem e piscinões. O ranking e a ficha abaixo trazem o mesmo conteúdo."
        />
        <button
          type="button"
          aria-pressed={is3d}
          onClick={() => setIs3d((v) => !v)}
          className="absolute left-2 top-2 rounded-md border border-surface-border bg-surface px-3 py-1 text-sm font-medium shadow"
        >
          {is3d ? "Ver em 2D" : "Ver em 3D"}
        </button>
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span>Bacias por setores em alto ou crítico agora: cinza 0 · laranja-claro 1–2 · laranja 3–9 · vermelho 10+</span>
        <span>Linha azul: rio ou córrego a céu aberto · tracejada cinza: canalizado fechado</span>
        <span>Círculo verde: piscinão</span>
      </p>
      {drainageNote && <p className="text-xs text-ink-muted">{drainageNote}</p>}
      {mode === "perfil" && (
        <p className="text-xs text-ink-muted">
          Clique no mapa para marcar os pontos do perfil (de 2 a 10, até 20 km no total).
        </p>
      )}
    </div>
  );
}
