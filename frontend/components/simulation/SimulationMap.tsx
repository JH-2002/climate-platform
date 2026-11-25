"use client";

/**
 * Mapa 2D da simulação (FR-107). Carregado só nesta página (import dinâmico).
 * Os setores simulados têm contorno roxo tracejado e o selo "SIMULAÇÃO" fica sempre visível
 * sobre o mapa (BR-100).
 */

import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJSON as GeoJSONData } from "geojson";
import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { circlePolygon } from "@/features/map/geometry";
import type { FeatureCollection } from "@/features/map/types";
import { CATEGORIES } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import type { CellInput, SimulationLayerProps } from "@/features/simulation/types";

const STYLE_URL = process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty";
const WORKER_URL = process.env.NEXT_PUBLIC_MAPLIBRE_WORKER_URL ?? "/vendor/maplibre-gl-worker.mjs";
const ATTRIBUTION = "SIMULAÇÃO — cenário hipotético · Setores: GeoSampa — Prefeitura de São Paulo";
const SAO_PAULO: [number, number] = [-46.6333, -23.5505];
const VIOLET = "#6d28d9";

type Json = Record<string, unknown>;

interface Props {
  layer?: FeatureCollection<SimulationLayerProps>;
  cell: CellInput | null;
  onPickCenter: (latitude: number, longitude: number) => void;
  onSelectSector: (id: number) => void;
}

function byCategory(): unknown[] {
  const pairs = (Object.keys(CATEGORIES) as RiskCategory[]).flatMap((c) => [c, CATEGORIES[c].color]);
  return ["match", ["get", "category"], ...pairs, CATEGORIES.UNKNOWN.color];
}

function cellCollection(cell: CellInput | null): Json {
  if (!cell) return { type: "FeatureCollection", features: [] };
  const ring = (factor: number, kind: string) => ({
    type: "Feature",
    properties: { kind },
    geometry: { type: "Polygon", coordinates: [circlePolygon(cell.longitude, cell.latitude, cell.radius_km * 1000 * factor, 64)] },
  });
  return {
    type: "FeatureCollection",
    features: [
      ring(1, "core"),
      ring(2, "edge"),
      { type: "Feature", properties: { kind: "center" }, geometry: { type: "Point", coordinates: [cell.longitude, cell.latitude] } },
    ],
  };
}

function setData(map: MapLibreMap, id: string, data: Json) {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as unknown as GeoJSONData);
}

export default function SimulationMap({ layer, cell, onPickCenter, onSelectSector }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const handlers = useRef({ onPickCenter, onSelectSector, cellMode: cell !== null, cell });
  const [ready, setReady] = useState(false);
  handlers.current = { onPickCenter, onSelectSector, cellMode: cell !== null, cell };

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    void (async () => {
      const maplibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      maplibre.setWorkerUrl(WORKER_URL);
      map = new maplibre.Map({
        container: container.current,
        style: STYLE_URL,
        center: SAO_PAULO,
        zoom: 9.6,
        attributionControl: { compact: false, customAttribution: ATTRIBUTION },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibre.ScaleControl({ unit: "metric" }), "bottom-left");
      map.on("load", () => {
        if (!map) return;
        for (const id of ["simulacao", "celula"]) {
          map.addSource(id, { type: "geojson", data: { type: "FeatureCollection", features: [] } as GeoJSONData });
        }
        map.addLayer({
          id: "simulacao-preenchimento",
          type: "fill",
          source: "simulacao",
          paint: { "fill-color": byCategory() as never, "fill-opacity": 0.75 },
        });
        map.addLayer({
          id: "simulacao-contorno",
          type: "line",
          source: "simulacao",
          // Setores são pequenos: na escala da cidade, o contorno na cor da categoria os torna
          // visíveis; de perto, o tracejado roxo marca que é simulação.
          paint: {
            "line-color": ["step", ["zoom"], byCategory(), 13, VIOLET] as never,
            "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 13, 1.5, 15, 2] as never,
            "line-dasharray": [2, 1],
          },
        });
        map.addLayer({
          id: "celula-borda",
          type: "line",
          source: "celula",
          filter: ["==", ["get", "kind"], "edge"],
          paint: { "line-color": VIOLET, "line-width": 1.5, "line-dasharray": [1, 2], "line-opacity": 0.8 },
        });
        map.addLayer({
          id: "celula-nucleo",
          type: "line",
          source: "celula",
          filter: ["==", ["get", "kind"], "core"],
          paint: { "line-color": VIOLET, "line-width": 2.5 },
        });
        map.addLayer({
          id: "celula-centro",
          type: "circle",
          source: "celula",
          filter: ["==", ["get", "kind"], "center"],
          paint: { "circle-radius": 6, "circle-color": VIOLET, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 },
        });
        map.on("click", "simulacao-preenchimento", (e: MapLayerMouseEvent) => {
          const id = Number(e.features?.[0]?.properties?.id);
          if (Number.isFinite(id)) handlers.current.onSelectSector(id);
        });
        map.on("click", (e: MapMouseEvent) => {
          if (!handlers.current.cellMode || !map) return;
          const hits = map.queryRenderedFeatures(e.point, { layers: ["simulacao-preenchimento"] });
          if (hits.length === 0) handlers.current.onPickCenter(e.lngLat.lat, e.lngLat.lng);
        });
        map.on("mouseenter", "simulacao-preenchimento", () => {
          if (map) map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "simulacao-preenchimento", () => {
          if (map) map.getCanvas().style.cursor = handlers.current.cellMode ? "crosshair" : "";
        });
        setReady(true);
      });
    })();
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "simulacao", (layer ?? { type: "FeatureCollection", features: [] }) as unknown as Json);
    // Resultado novo com célula: enquadra a área atingida (duas vezes o raio).
    const c = handlers.current.cell;
    if (layer && c) {
      const ring = circlePolygon(c.longitude, c.latitude, c.radius_km * 2000, 16);
      const lons = ring.map((p) => p[0]!);
      const lats = ring.map((p) => p[1]!);
      map.fitBounds(
        [
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)],
        ],
        { padding: 24, duration: 0 },
      );
    }
  }, [ready, layer]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "celula", cellCollection(cell));
    map.getCanvas().style.cursor = cell ? "crosshair" : "";
  }, [ready, cell]);

  return (
    <div className="relative">
      <div
        ref={container}
        className="h-[55vh] min-h-80 w-full overflow-hidden rounded-lg border-2 border-violet-700"
        role="region"
        aria-label="Mapa da simulação. A lista de setores abaixo traz o mesmo conteúdo."
      />
      <p
        aria-hidden="true"
        className="pointer-events-none absolute left-2 top-2 rounded bg-violet-700 px-2 py-1 text-xs font-bold uppercase tracking-wide text-white"
      >
        Simulação
      </p>
      {cell && (
        <p className="mt-1 text-xs text-ink-muted">
          Clique fora dos setores para mover o centro da célula. Linha cheia: raio (100% da chuva); tracejada: duas vezes o
          raio (0%).
        </p>
      )}
    </div>
  );
}
