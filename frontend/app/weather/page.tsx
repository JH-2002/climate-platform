"use client";

import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DailyTable } from "@/components/weather/DailyTable";
import { HourlyChart } from "@/components/weather/HourlyChart";
import { LocationPicker } from "@/components/weather/LocationPicker";
import { NearbyStations } from "@/components/weather/NearbyStations";
import { NowCard } from "@/components/weather/NowCard";
import { RainOutlook } from "@/components/weather/RainOutlook";
import { SourceNote } from "@/components/weather/SourceNote";
import { useLocations } from "@/features/locations/useLocations";
import { useSourcesStatus } from "@/features/sources/useSourcesStatus";
import { useForecast, useNearbyStations } from "@/features/weather/hooks";
import { ApiError } from "@/lib/api-client";
import { resolveSelectedLocation } from "@/features/locations/selection";

function WeatherDashboard() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const locations = useLocations();
  const selected = resolveSelectedLocation(params, locations.locations, locations.defaultId);

  const forecast = useForecast(selected.lat, selected.lon);
  const nearby = useNearbyStations(selected.lat, selected.lon);
  const sources = useSourcesStatus();
  const observationsAvailable =
    sources.data?.items.find((s) => s.code === "inmet-observations")?.freshness === "FRESH";

  function select(location: { lat: number; lon: number; name: string }) {
    const query = new URLSearchParams({
      lat: String(location.lat),
      lon: String(location.lon),
      nome: location.name,
    });
    router.replace(`${pathname}?${query}`, { scroll: false });
  }

  const notFound = forecast.error instanceof ApiError && forecast.error.status === 404;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Clima</h1>
        <p className="text-sm text-ink-muted">
          {selected.name} · {selected.lat.toFixed(4)}, {selected.lon.toFixed(4)}
        </p>
      </header>

      <LocationPicker
        locations={locations.locations}
        defaultId={locations.defaultId}
        selected={selected}
        persisted={locations.persisted}
        onSelect={select}
        onAdd={(l) => {
          locations.add(l);
          select(l);
        }}
        onRemove={locations.remove}
        onSetDefault={locations.setDefault}
      />

      {forecast.isPending && (
        <div role="status" aria-live="polite" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
          <span className="sr-only">Carregando a previsão…</span>
        </div>
      )}

      {forecast.isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface p-4">
          <p className="text-sm text-ink-muted">
            {notFound
              ? forecast.error.message
              : `Não foi possível carregar a previsão. ${forecast.error.message}`}
          </p>
          {!notFound && (
            <button
              type="button"
              onClick={() => void forecast.refetch()}
              className="rounded-md border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent hover:text-white"
            >
              Tentar novamente
            </button>
          )}
        </div>
      )}

      {forecast.data && (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <NowCard now={forecast.data.now} />
            <RainOutlook
              outlook={forecast.data.precipitation_outlook}
              observationsAvailable={observationsAvailable}
            />
          </div>
          <HourlyChart hours={forecast.data.hourly} />
          <DailyTable days={forecast.data.daily} />
          <SourceNote forecast={forecast.data} />
          <p className="text-xs text-ink-muted">
            Modelos de previsão representam mal tempestades locais intensas. Para alertas, siga a
            Defesa Civil e o CGE.
          </p>
        </>
      )}

      <NearbyStations
        state={nearby.isPending ? "loading" : nearby.isError ? "error" : "success"}
        stations={nearby.data}
        observationsAvailable={observationsAvailable}
      />
    </div>
  );
}

export default function WeatherPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">Carregando…</p>}>
      <WeatherDashboard />
    </Suspense>
  );
}
