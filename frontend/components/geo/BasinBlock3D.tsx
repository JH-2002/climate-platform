"use client";

/**
 * Bloco 3D da bacia (FR-128 a FR-130), com MapLibre sobre o relevo do Copernicus servido pelo
 * backend: o 3D usa o mesmo relevo dos cálculos (ADR-013). Carregado só nesta vista.
 * Teclado: setas movem; Shift + setas giram e inclinam; + e − aproximam (padrão do MapLibre).
 */

import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJSON as GeoJSONData } from "geojson";
import type { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { drainageUrl, terrainTilesUrl } from "@/features/geo/api";
import type { BasinBlock, BasinLayerProps } from "@/features/geo/types";
import type { Feature, FeatureCollection } from "@/features/map/types";
import { CATEGORIES } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import { apiGet } from "@/lib/api-client";
import { formatNumber } from "@/lib/format";

const STYLE_URL = process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty";
const WORKER_URL = process.env.NEXT_PUBLIC_MAPLIBRE_WORKER_URL ?? "/vendor/maplibre-gl-worker.mjs";
const PITCH = 62;
const BEARING = -20;

interface Props {
  block: BasinBlock;
  basin?: Feature<BasinLayerProps>;
  reservoirs?: FeatureCollection<Record<string, unknown>>;
  title: string;
  onError: (message: string) => void;
}

function categoryColors(): unknown[] {
  const pairs = (Object.keys(CATEGORIES) as RiskCategory[]).flatMap((c) => [c, CATEGORIES[c].color]);
  return ["match", ["get", "category"], ...pairs, CATEGORIES.UNKNOWN.color];
}

/** Mundo com a bacia recortada: tudo fora dela fica esmaecido. */
function outsideMask(basin: Feature<BasinLayerProps> | undefined): unknown {
  const world = [
    [-180, -85],
    [180, -85],
    [180, 85],
    [-180, 85],
    [-180, -85],
  ];
  const geometry = basin?.geometry as unknown as { type: string; coordinates: number[][][] | number[][][][] } | undefined;
  const holes =
    geometry?.type === "Polygon"
      ? [(geometry.coordinates as number[][][])[0]]
      : geometry?.type === "MultiPolygon"
        ? (geometry.coordinates as number[][][][]).map((p) => p[0])
        : [];
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [world, ...holes] } }],
  };
}

function sectorPoints(block: BasinBlock): unknown {
  return {
    type: "FeatureCollection",
    features: block.sectors.map((s) => ({
      type: "Feature",
      properties: { category: s.category, code: s.code },
      geometry: { type: "Point", coordinates: [s.longitude, s.latitude] },
    })),
  };
}

function setData(map: MapLibreMap, id: string, data: unknown) {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as GeoJSONData);
}

/** Imagem para exportar: o mapa mais título, legenda e fontes (FR-130). */
function composeExport(map: MapLibreMap, block: BasinBlock, title: string, exaggeration: number): string {
  const source = map.getCanvas();
  const footer = 96;
  const out = document.createElement("canvas");
  out.width = source.width;
  out.height = source.height + footer;
  const ctx = out.getContext("2d");
  if (!ctx) return source.toDataURL("image/png");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.drawImage(source, 0, 0);
  ctx.fillStyle = "#111827";
  ctx.font = "bold 18px system-ui, sans-serif";
  ctx.fillText(title, 12, source.height + 24);
  ctx.font = "13px system-ui, sans-serif";
  let x = 12;
  for (const cat of ["CRITICAL", "HIGH", "MODERATE", "LOW", "UNKNOWN"] as RiskCategory[]) {
    ctx.fillStyle = CATEGORIES[cat].color;
    ctx.beginPath();
    ctx.arc(x + 6, source.height + 44, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#111827";
    ctx.fillText(CATEGORIES[cat].label, x + 16, source.height + 49);
    x += ctx.measureText(CATEGORIES[cat].label).width + 34;
  }
  ctx.fillStyle = "#4b5563";
  ctx.font = "11px system-ui, sans-serif";
  ctx.fillText(
    `${block.banner ?? "Estimativa experimental — não é alerta oficial"} · exagero vertical ${formatNumber(exaggeration, 1)}×`,
    12,
    source.height + 70,
  );
  ctx.fillText(`Relevo: Copernicus DEM GLO-30 (ESA) · ${block.hydro_attribution} · Mapa: OpenFreeMap/OpenStreetMap`, 12, source.height + 86);
  return out.toDataURL("image/png");
}

export default function BasinBlock3D({ block, basin, reservoirs, title, onError }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [exaggeration, setExaggeration] = useState(2);

  function resetView(map: MapLibreMap | null = mapRef.current, duration = 600) {
    if (!map) return;
    const b = block.bounds;
    map.fitBounds(
      [
        [b.west, b.south],
        [b.east, b.north],
      ],
      { padding: 40, pitch: PITCH, bearing: BEARING, duration },
    );
  }

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
        bounds: [
          [block.bounds.west, block.bounds.south],
          [block.bounds.east, block.bounds.north],
        ],
        fitBoundsOptions: { padding: 40 },
        maxPitch: 80,
        canvasContextAttributes: { preserveDrawingBuffer: true },
        attributionControl: {
          compact: false,
          customAttribution: `Relevo: Copernicus DEM GLO-30 (ESA) · ${block.hydro_attribution}`,
        },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibre.ScaleControl({ unit: "metric" }), "bottom-left");
      map.on("error", (e) => {
        if (/terrain|relief|geo\/terrain/i.test(String(e.error?.message ?? ""))) onError("Relevo indisponível agora.");
      });
      map.on("load", async () => {
        if (!map) return;
        const tiles = terrainTilesUrl(window.location.origin);
        map.addSource("relevo", { type: "raster-dem", tiles: [tiles], encoding: "terrarium", tileSize: 256, minzoom: 6, maxzoom: 14 });
        map.addSource("relevo-sombra", {
          type: "raster-dem",
          tiles: [tiles],
          encoding: "terrarium",
          tileSize: 256,
          minzoom: 6,
          maxzoom: 14,
        });
        map.addLayer({
          id: "sombreado",
          type: "hillshade",
          source: "relevo-sombra",
          paint: { "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "#3d4650" },
        });
        for (const id of ["fora", "drenagem", "piscinoes", "setores"]) {
          map.addSource(id, { type: "geojson", data: { type: "FeatureCollection", features: [] } as GeoJSONData });
        }
        map.addLayer({ id: "fora-da-bacia", type: "fill", source: "fora", paint: { "fill-color": "#ffffff", "fill-opacity": 0.6 } });
        map.addLayer({
          id: "drenagem-linhas",
          type: "line",
          source: "drenagem",
          paint: {
            "line-color": ["case", ["get", "open_channel"], "#1d6fd6", "#7b8fa6"],
            "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1, 15, 3],
          },
        });
        map.addLayer({
          id: "piscinoes-pontos",
          type: "circle",
          source: "piscinoes",
          paint: { "circle-radius": 6, "circle-color": "#0f766e", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 },
        });
        map.addLayer({
          id: "setores-pontos",
          type: "circle",
          source: "setores",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 4, 15, 9],
            "circle-color": categoryColors() as never,
            "circle-stroke-color": "#111827",
            "circle-stroke-width": 1,
          },
        });
        map.setTerrain({ source: "relevo", exaggeration });
        resetView(map, 0);
        setReady(true);
        try {
          const b = block.bounds;
          const { data } = await apiGet<FeatureCollection<Record<string, unknown>>>(
            drainageUrl([b.west, b.south, b.east, b.north], 13),
          );
          if (map) setData(map, "drenagem", data);
        } catch {
          onError("Drenagem indisponível agora.");
        }
      });
    })();
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // O bloco é recriado quando muda a bacia (chave no componente pai).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "fora", outsideMask(basin));
    setData(map, "setores", sectorPoints(block));
    if (reservoirs) setData(map, "piscinoes", reservoirs);
  }, [ready, basin, block, reservoirs]);

  useEffect(() => {
    const map = mapRef.current;
    if (ready && map) map.setTerrain({ source: "relevo", exaggeration });
  }, [ready, exaggeration]);

  function exportImage() {
    const map = mapRef.current;
    if (!map) return;
    map.once("render", () => {
      const link = document.createElement("a");
      link.href = composeExport(map, block, title, exaggeration);
      link.download = `bacia-${block.basin_id}${block.simulation_id ? "-simulacao" : ""}.png`;
      link.click();
    });
    map.triggerRepaint();
  }

  return (
    <div className="space-y-2">
      <div
        ref={container}
        className="h-[62vh] min-h-96 w-full overflow-hidden rounded-lg border border-surface-border"
        role="region"
        aria-label={`Bloco 3D da bacia ${block.name}. Use as setas para mover e Shift com as setas para girar. A tabela abaixo traz os mesmos setores.`}
      />
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2">
          Exagero vertical
          <input
            type="range"
            min={1}
            max={5}
            step={0.5}
            value={exaggeration}
            onChange={(e) => setExaggeration(Number(e.target.value))}
            aria-valuetext={`${formatNumber(exaggeration, 1)} vezes`}
          />
          <span className="tabular-nums">{formatNumber(exaggeration, 1)}×</span>
        </label>
        <button type="button" onClick={() => resetView()} className="rounded-md border border-surface-border px-3 py-1">
          Reiniciar a vista
        </button>
        <button type="button" onClick={exportImage} className="rounded-md border border-accent px-3 py-1 font-medium text-accent">
          Exportar imagem (PNG)
        </button>
      </div>
    </div>
  );
}
