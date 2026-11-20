"use client";

/**
 * Mapa 2D/3D com MapLibre GL (ADR-009). Carregado só nesta página (import dinâmico).
 * Conteúdo de popups é montado com textContent (sem HTML vindo de dados).
 */

import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJSON as GeoJSONData, Point } from "geojson";
import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import type { SavedLocation } from "@/features/locations/store";
import { COLUMN_MAX_M, STATION_STATUS, circlePolygon, columnHeight, rainClass } from "@/features/map/geometry";
import type { LayerId, MapMode } from "@/features/map/state";
import type { FeatureCollection, ForecastPointProps, RegionFeature, StationProps } from "@/features/map/types";
import { CATEGORIES, OCCURRENCE_TYPE_LABELS, categoryLabel, titleCase } from "@/features/risk/categories";
import { riskHref } from "@/features/risk/state";
import type { OccurrenceProps, RiskCategory, RiskLayer, RiskLayerProps } from "@/features/risk/types";
import { formatDateTime, formatNumber } from "@/lib/format";

const STYLE_URL = process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty";
const TERRAIN_URL =
  process.env.NEXT_PUBLIC_TERRAIN_TILES_URL ??
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
// Copiado por scripts/copy-maplibre-worker.mjs (pré-dev/pré-build).
const WORKER_URL = process.env.NEXT_PUBLIC_MAPLIBRE_WORKER_URL ?? "/vendor/maplibre-gl-worker.mjs";
const TERRAIN_ATTRIBUTION =
  '<a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md" target="_blank" rel="noopener">Relevo: Terrain Tiles (Mapzen/AWS)</a>';
const DATA_ATTRIBUTION =
  "Previsão: Open-Meteo.com (CC BY 4.0) · Estações: INMET · Setores e ocorrências: GeoSampa — Prefeitura de São Paulo";
const SAO_PAULO: [number, number] = [-46.6333, -23.5505];
const PITCH_3D = 60;
const EXAGGERATION = 1.5;

const LAYER_GROUPS: Record<LayerId, string[]> = {
  estacoes: ["estacoes-circulos"],
  chuva: ["chuva-2d", "chuva-3d"],
  risco: ["risco-2d", "risco-contorno", "risco-3d"],
  ocorrencias: ["ocorrencias-pontos"],
  locais: ["locais-circulos"],
  regiao: ["regiao-contorno"],
};

interface MapViewProps {
  mode: MapMode;
  layers: LayerId[];
  region?: RegionFeature;
  stations?: FeatureCollection<StationProps>;
  forecast?: FeatureCollection<ForecastPointProps>;
  risk?: RiskLayer;
  occurrences?: FeatureCollection<OccurrenceProps>;
  locations: SavedLocation[];
  reducedMotion: boolean;
  onError: (message: string) => void;
}

type Json = Record<string, unknown>;

function emptyCollection(): Json {
  return { type: "FeatureCollection", features: [] };
}

function forecastPoints(fc?: FeatureCollection<ForecastPointProps>): Json {
  if (!fc) return emptyCollection();
  return {
    type: "FeatureCollection",
    features: fc.features.map((f) => ({
      ...f,
      properties: { ...f.properties, cor: rainClass(f.properties.precipitation_24h).color },
    })),
  };
}

function forecastColumns(fc?: FeatureCollection<ForecastPointProps>): Json {
  if (!fc) return emptyCollection();
  return {
    type: "FeatureCollection",
    features: fc.features.map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      const mm = f.properties.precipitation_24h;
      return {
        type: "Feature",
        id: f.id,
        geometry: { type: "Polygon", coordinates: [circlePolygon(lon, lat, 900)] },
        properties: { ...f.properties, cor: rainClass(mm).color, altura: columnHeight(mm) },
      };
    }),
  };
}

function locationsCollection(locations: SavedLocation[]): Json {
  return {
    type: "FeatureCollection",
    features: locations.map((l) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [l.lon, l.lat] },
      properties: { name: l.name, lat: l.lat, lon: l.lon },
    })),
  };
}

function popupContent(title: string, lines: string[], link?: { href: string; label: string }): HTMLElement {
  const root = document.createElement("div");
  root.className = "space-y-1 text-sm";
  const h = document.createElement("p");
  h.className = "font-semibold";
  h.textContent = title;
  root.append(h);
  for (const line of lines) {
    const p = document.createElement("p");
    p.textContent = line;
    root.append(p);
  }
  if (link) {
    const a = document.createElement("a");
    a.href = link.href;
    a.textContent = link.label;
    a.className = "font-medium text-accent underline";
    root.append(a);
  }
  return root;
}

/** Expressão MapLibre: categoria -> valor (cor ou altura), com cinza/mínimo como padrão. */
function byCategory(field: "color" | "height"): unknown[] {
  const pairs = (Object.keys(CATEGORIES) as RiskCategory[]).flatMap((c) => [c, CATEGORIES[c][field]]);
  return ["match", ["get", "category"], ...pairs, CATEGORIES.UNKNOWN[field]];
}

function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  return d && m && y ? `${d}/${m}/${y}` : isoDate;
}

function weatherHref(lat: number, lon: number, name: string): string {
  return `/weather?${new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4), nome: name })}`;
}

function setData(map: MapLibreMap, id: string, data: Json) {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as unknown as GeoJSONData);
}

export default function MapView(props: MapViewProps) {
  const { mode, layers, region, stations, forecast, risk, occurrences, locations, reducedMotion, onError } = props;
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);

  // Cria o mapa uma vez.
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
        zoom: 10,
        pitch: 0,
        maxPitch: 75,
        attributionControl: { compact: false, customAttribution: DATA_ATTRIBUTION },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibre.FullscreenControl(), "top-right");
      map.addControl(new maplibre.ScaleControl({ unit: "metric" }), "bottom-left");
      map.on("error", (event) => {
        const message = event.error?.message ?? "";
        if (/style|Failed to fetch/i.test(message)) onError("Não foi possível carregar o mapa base.");
      });

      map.on("load", () => {
        if (!map) return;
        map.addSource("terreno", {
          type: "raster-dem",
          tiles: [TERRAIN_URL],
          encoding: "terrarium",
          tileSize: 256,
          maxzoom: 15,
          attribution: TERRAIN_ATTRIBUTION,
        });
        map.addSource("terreno-sombra", {
          type: "raster-dem",
          tiles: [TERRAIN_URL],
          encoding: "terrarium",
          tileSize: 256,
          maxzoom: 15,
        });
        map.addLayer({
          id: "relevo-sombreado",
          type: "hillshade",
          source: "terreno-sombra",
          paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#47515a" },
        });

        for (const id of ["regiao", "risco", "ocorrencias", "estacoes", "chuva-pontos", "chuva-colunas", "locais"]) {
          map.addSource(id, { type: "geojson", data: emptyCollection() as unknown as GeoJSONData });
        }
        map.addLayer({
          id: "regiao-contorno",
          type: "line",
          source: "regiao",
          paint: { "line-color": "#0b5c7a", "line-width": 2, "line-dasharray": [3, 2] },
        });
        // Risco estimado (spec 005): preenchimento em 2D, extrusão por categoria em 3D.
        map.addLayer({
          id: "risco-2d",
          type: "fill",
          source: "risco",
          paint: { "fill-color": byCategory("color") as never, "fill-opacity": 0.55 },
        });
        map.addLayer({
          id: "risco-contorno",
          type: "line",
          source: "risco",
          paint: { "line-color": byCategory("color") as never, "line-width": 1.5 },
        });
        map.addLayer({
          id: "risco-3d",
          type: "fill-extrusion",
          source: "risco",
          paint: {
            "fill-extrusion-color": byCategory("color") as never,
            "fill-extrusion-height": byCategory("height") as never,
            "fill-extrusion-base": 0,
            "fill-extrusion-opacity": 0.8,
          },
        });
        map.addLayer({
          id: "chuva-2d",
          type: "circle",
          source: "chuva-pontos",
          paint: {
            "circle-color": ["get", "cor"],
            "circle-opacity": 0.75,
            "circle-radius": ["interpolate", ["linear"], ["get", "precipitation_24h"], 0, 10, 50, 40],
            "circle-stroke-color": "#08465d",
            "circle-stroke-width": 1,
          },
        });
        map.addLayer({
          id: "chuva-3d",
          type: "fill-extrusion",
          source: "chuva-colunas",
          paint: {
            "fill-extrusion-color": ["get", "cor"],
            "fill-extrusion-height": ["get", "altura"],
            "fill-extrusion-base": 0,
            "fill-extrusion-opacity": 0.85,
          },
        });
        map.addLayer({
          id: "ocorrencias-pontos",
          type: "circle",
          source: "ocorrencias",
          paint: {
            "circle-radius": 4,
            "circle-color": "#1f2937",
            "circle-opacity": 0.8,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1,
          },
        });
        map.addLayer({
          id: "estacoes-circulos",
          type: "circle",
          source: "estacoes",
          paint: {
            "circle-radius": 7,
            "circle-color": [
              "match",
              ["get", "status"],
              "OPERATIONAL",
              STATION_STATUS.OPERATIONAL!.color,
              "FAULT",
              STATION_STATUS.FAULT!.color,
              STATION_STATUS.UNKNOWN!.color,
            ],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
          },
        });
        map.addLayer({
          id: "locais-circulos",
          type: "circle",
          source: "locais",
          paint: {
            "circle-radius": 6,
            "circle-color": "#ffffff",
            "circle-stroke-color": "#0b5c7a",
            "circle-stroke-width": 3,
          },
        });

        const popup = new maplibre.Popup({ closeButton: true, maxWidth: "280px" });
        const showStation = (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties as unknown as StationProps;
          const [lon, lat] = (f.geometry as Point).coordinates as [number, number];
          popup
            .setLngLat([lon, lat])
            .setDOMContent(
              popupContent(
                `${p.name} (${p.code})`,
                [
                  `Situação: ${STATION_STATUS[p.status]?.label ?? p.status}`,
                  p.altitude_m != null ? `Altitude: ${formatNumber(Number(p.altitude_m), 0)} m` : "Altitude: —",
                  "Medições: aguardando token do INMET",
                ],
                { href: weatherHref(lat, lon, p.name), label: "Ver clima neste ponto" },
              ),
            )
            .addTo(map!);
        };
        const showForecast = (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties as unknown as ForecastPointProps;
          const complete = String(p.precipitation_24h_complete) === "true";
          const coords =
            f.geometry.type === "Point"
              ? ((f.geometry as Point).coordinates as [number, number])
              : ([e.lngLat.lng, e.lngLat.lat] as [number, number]);
          const temp = p.air_temperature_now == null ? null : Number(p.air_temperature_now);
          popup
            .setLngLat(coords)
            .setDOMContent(
              popupContent(
                "Ponto de previsão (modelo)",
                [
                  `Chuva prevista em 24 h: ${formatNumber(Number(p.precipitation_24h))} mm${complete ? "" : ` (parcial: ${p.precipitation_24h_hours} h)`}`,
                  `Temperatura estimada agora: ${formatNumber(temp)} °C`,
                  `Coleta: ${formatDateTime(String(p.issued_at))}`,
                  "Estimativa de modelo — não é medição.",
                ],
                { href: weatherHref(coords[1], coords[0], "Ponto de previsão"), label: "Ver previsão completa" },
              ),
            )
            .addTo(map!);
        };
        const showRisk = (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties as unknown as RiskLayerProps;
          const p1h = p.p1h_max_mm == null ? null : Number(p.p1h_max_mm);
          const p24 = p.p24_mm == null ? null : Number(p.p24_mm);
          popup
            .setLngLat(e.lngLat)
            .setDOMContent(
              popupContent(
                `Setor ${p.code} — ${titleCase(p.name ?? null)}`,
                [
                  `Risco estimado: ${categoryLabel(String(p.category))}`,
                  `Subprefeitura: ${titleCase(p.subprefecture ?? null)} · grau R${p.grade}`,
                  p1h === null
                    ? "Chuva prevista: indisponível"
                    : `Chuva prevista: até ${formatNumber(p1h)} mm/h · ${formatNumber(p24)} mm em 24 h`,
                  "Estimativa experimental do sistema — não é alerta oficial.",
                ],
                { href: riskHref(Number(p.id)), label: "Ver por que esta estimativa" },
              ),
            )
            .addTo(map!);
        };
        const showOccurrence = (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties as unknown as OccurrenceProps;
          const [lon, lat] = (f.geometry as Point).coordinates as [number, number];
          popup
            .setLngLat([lon, lat])
            .setDOMContent(
              popupContent(`${OCCURRENCE_TYPE_LABELS[p.type] ?? p.type} registrado`, [
                `Data: ${formatDate(String(p.occurred_on))}`,
                `Subprefeitura: ${titleCase(p.subprefecture ?? null)}`,
                "Fonte: GeoSampa (Defesa Civil). Registro de atendimento; pode não incluir todos os eventos.",
              ]),
            )
            .addTo(map!);
        };
        map.on("click", "risco-2d", showRisk);
        map.on("click", "risco-3d", showRisk);
        map.on("click", "ocorrencias-pontos", showOccurrence);
        map.on("click", "estacoes-circulos", showStation);
        map.on("click", "chuva-2d", showForecast);
        map.on("click", "chuva-3d", showForecast);
        for (const id of [
          "estacoes-circulos",
          "chuva-2d",
          "chuva-3d",
          "locais-circulos",
          "risco-2d",
          "risco-3d",
          "ocorrencias-pontos",
        ]) {
          map.on("mouseenter", id, () => (map!.getCanvas().style.cursor = "pointer"));
          map.on("mouseleave", id, () => (map!.getCanvas().style.cursor = ""));
        }
        map.on("click", "locais-circulos", (e) => {
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties as { name: string; lat: number; lon: number };
          popup
            .setLngLat([Number(p.lon), Number(p.lat)])
            .setDOMContent(
              popupContent(p.name, ["Local salvo neste navegador"], {
                href: weatherHref(Number(p.lat), Number(p.lon), p.name),
                label: "Ver clima deste local",
              }),
            )
            .addTo(map!);
        });
        setReady(true);
      });
    })().catch(() => onError("Não foi possível iniciar o mapa neste navegador."));

    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // O mapa é criado uma única vez; mudanças de props são aplicadas pelos efeitos abaixo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Dados das camadas.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "regiao", (region as unknown as Json) ?? emptyCollection());
    setData(map, "estacoes", (stations as unknown as Json) ?? emptyCollection());
    setData(map, "chuva-pontos", forecastPoints(forecast));
    setData(map, "chuva-colunas", forecastColumns(forecast));
    setData(map, "locais", locationsCollection(locations));
    setData(map, "risco", (risk as unknown as Json) ?? emptyCollection());
    setData(map, "ocorrencias", (occurrences as unknown as Json) ?? emptyCollection());
  }, [ready, region, stations, forecast, risk, occurrences, locations]);

  // Modo 2D/3D e visibilidade das camadas.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const is3d = mode === "3d";
    map.setTerrain(is3d ? { source: "terreno", exaggeration: EXAGGERATION } : null);
    for (const [group, ids] of Object.entries(LAYER_GROUPS) as [LayerId, string[]][]) {
      for (const id of ids) {
        let visible = layers.includes(group);
        if (id === "chuva-2d") visible &&= !is3d;
        if (id === "chuva-3d") visible &&= is3d;
        if (id === "risco-2d") visible &&= !is3d;
        if (id === "risco-3d") visible &&= is3d;
        map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      }
    }
    const camera = { pitch: is3d ? PITCH_3D : 0, bearing: is3d ? -20 : 0 };
    if (reducedMotion) map.jumpTo(camera);
    else map.easeTo({ ...camera, duration: 900 });
  }, [ready, mode, layers, reducedMotion]);

  return (
    <div
      ref={container}
      className="h-[60vh] min-h-80 w-full overflow-hidden rounded-lg border border-surface-border"
      role="region"
      aria-label={`Mapa ${mode === "3d" ? "3D com relevo" : "2D"}. Use as setas para mover, + e − para zoom. Os mesmos dados estão na lista abaixo do mapa.`}
      data-max-column-m={COLUMN_MAX_M}
    />
  );
}
