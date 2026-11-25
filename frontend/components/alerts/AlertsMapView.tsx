"use client";

/**
 * Mapa 2D dos alertas oficiais vigentes e próximos (FR-146). Carregado só na página de alertas.
 * A lista ao lado tem as mesmas informações (NFR-144). Popups montados com textContent.
 */

import "maplibre-gl/dist/maplibre-gl.css";
import { basePath } from "@/lib/demo";
import type { GeoJSON as GeoJSONData } from "geojson";
import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { OFFICIAL_COLORS } from "@/components/alerts/mapColors";
import { alertHref } from "@/features/alerts/labels";
import type { AlertLayerProps } from "@/features/alerts/types";
import type { FeatureCollection } from "@/features/map/types";
import { DEFAULT_MAP_STYLE_URL } from "@/lib/map-sources.mjs";

const STYLE_URL = process.env.NEXT_PUBLIC_MAP_STYLE_URL || DEFAULT_MAP_STYLE_URL;
const WORKER_URL = process.env.NEXT_PUBLIC_MAPLIBRE_WORKER_URL ?? `${basePath()}/vendor/maplibre-gl-worker.mjs`;
const CITY_BOUNDS: [[number, number], [number, number]] = [
  [-46.83, -24.01],
  [-46.36, -23.35],
];

function popup(props: AlertLayerProps): HTMLElement {
  const root = document.createElement("div");
  root.className = "space-y-1 text-sm";
  const label = document.createElement("p");
  label.className = "font-semibold";
  label.textContent = `${props.category_label} · ${props.severity_label}`;
  const text = document.createElement("p");
  text.textContent = props.headline ?? "";
  const link = document.createElement("a");
  link.href = `${basePath()}${alertHref(Number(props.id))}`;
  link.textContent = "Ver alerta";
  link.className = "font-medium text-accent underline";
  root.append(label, text, link);
  return root;
}

export default function AlertsMapView({
  layer,
  onError,
}: {
  layer: FeatureCollection<AlertLayerProps> | undefined;
  onError: (message: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);

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
        bounds: CITY_BOUNDS,
        fitBoundsOptions: { padding: 16 },
        // A página rola por cima do mapa: zoom com Ctrl + roda (ou dois dedos no celular).
        cooperativeGestures: true,
        attributionControl: {
          compact: false,
          customAttribution: "Alertas: Defesa Civil (IDAP/MIDR) e INMET · Subprefeituras: GeoSampa",
        },
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
      map.on("load", () => {
        if (!map) return;
        map.addSource("alertas", { type: "geojson", data: { type: "FeatureCollection", features: [] } as GeoJSONData });
        const color = ["match", ["get", "category"], "CIVIL_DEFENSE", OFFICIAL_COLORS.CIVIL_DEFENSE, OFFICIAL_COLORS.WEATHER_WARNING];
        map.addLayer({
          id: "alertas-area",
          type: "fill",
          source: "alertas",
          paint: { "fill-color": color as never, "fill-opacity": ["case", ["==", ["get", "status"], "ACTIVE"], 0.14, 0.05] },
        });
        map.addLayer({
          id: "alertas-contorno",
          type: "line",
          source: "alertas",
          paint: {
            "line-color": color as never,
            "line-width": 2,
            "line-dasharray": ["case", ["==", ["get", "status"], "ACTIVE"], ["literal", [1, 0]], ["literal", [2, 2]]] as never,
          },
        });
        const info = new maplibre.Popup({ closeButton: true, maxWidth: "280px" });
        map.on("click", "alertas-area", (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          info.setLngLat(e.lngLat).setDOMContent(popup(f.properties as unknown as AlertLayerProps)).addTo(map!);
        });
        setReady(true);
      });
    })().catch(() => onError("Não foi possível iniciar o mapa neste navegador."));
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("alertas") as GeoJSONSource | undefined)?.setData(
      (layer ?? { type: "FeatureCollection", features: [] }) as unknown as GeoJSONData,
    );
  }, [ready, layer]);

  return (
    <div
      ref={container}
      className="h-80 w-full overflow-hidden rounded-lg border border-surface-border"
      role="region"
      aria-label="Mapa das áreas dos alertas oficiais. A lista de alertas tem as mesmas informações."
    />
  );
}
