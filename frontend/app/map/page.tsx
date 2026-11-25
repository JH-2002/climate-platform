"use client";

import dynamic from "next/dynamic";
import { useReducedMotion, useWebGL } from "@/features/map/useCapabilities";
import { Suspense, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { MapControls } from "@/components/map/MapControls";
import { MapFeatureList } from "@/components/map/MapFeatureList";
import { MapLegend } from "@/components/map/MapLegend";
import { RiskDisclaimer } from "@/components/risk/RiskDisclaimer";
import { useLocations } from "@/features/locations/useLocations";
import { useMapLayers } from "@/features/map/hooks";
import { parseMapState, serializeMapState, toggleLayer, type MapState } from "@/features/map/state";

// A biblioteca de mapa só é carregada nesta página e só no navegador (NFR-050).
const MapView = dynamic(() => import("@/components/map/MapView"), {
  ssr: false,
  loading: () => (
    <div role="status" className="h-[60vh] min-h-80 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">Carregando o mapa…</span>
    </div>
  ),
});

function MapPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const state = parseMapState(params);
  const { region, stations, forecast, risk, occurrences, alerts } = useMapLayers();
  const locations = useLocations();
  const webgl = useWebGL();
  const reducedMotion = useReducedMotion();
  const [mapError, setMapError] = useState<string | null>(null);


  function update(next: MapState) {
    router.replace(`${pathname}?${serializeMapState(next)}`, { scroll: false });
  }

  const loadError =
    region.isError || stations.isError || forecast.isError || risk.isError || occurrences.isError;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Mapa</h1>
        <p className="text-sm text-ink-muted">
          Estações oficiais, chuva prevista, risco estimado de alagamento e relevo. Em 3D, arraste
          com o botão direito (ou Ctrl + arrastar) para inclinar e girar.
        </p>
      </header>

      <MapControls
        mode={state.mode}
        layers={state.layers}
        webgl={webgl !== false}
        onModeChange={(mode) => update({ ...state, mode })}
        onToggleLayer={(id) => update(toggleLayer(state, id))}
      />

      {state.layers.includes("risco") && <RiskDisclaimer compact />}

      {loadError && (
        <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
          Algumas camadas não puderam ser carregadas. O mapa mostra o que estiver disponível.
        </p>
      )}
      {mapError && (
        <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
          {mapError} Os dados continuam disponíveis na lista abaixo.
        </p>
      )}

      {webgl === false ? (
        <p role="status" className="rounded-lg border border-surface-border bg-surface p-4 text-sm">
          Este navegador não oferece WebGL, necessário para desenhar o mapa. Os mesmos dados estão na
          lista abaixo.
        </p>
      ) : webgl === null ? null : (
        <MapView
          mode={state.mode}
          layers={state.layers}
          region={region.data}
          stations={stations.data}
          forecast={forecast.data}
          risk={risk.data}
          occurrences={occurrences.data}
          alerts={alerts.data}
          locations={locations.locations}
          reducedMotion={reducedMotion}
          onError={setMapError}
        />
      )}

      <MapLegend mode={state.mode} />
      <MapFeatureList stations={stations.data} forecast={forecast.data} />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">Carregando…</p>}>
      <MapPage />
    </Suspense>
  );
}
