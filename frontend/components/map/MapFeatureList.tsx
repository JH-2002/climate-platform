import Link from "next/link";
import { STATION_STATUS, rainClass } from "@/features/map/geometry";
import type { FeatureCollection, ForecastPointProps, StationProps } from "@/features/map/types";
import { formatDateTime, formatNumber } from "@/lib/format";

interface MapFeatureListProps {
  stations?: FeatureCollection<StationProps>;
  forecast?: FeatureCollection<ForecastPointProps>;
}

function weatherHref(lat: number, lon: number, name: string): string {
  return `/weather?${new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4), nome: name })}`;
}

/** Mesmas informações do mapa em forma de lista (FR-057): o mapa não é a única forma de acesso. */
export function MapFeatureList({ stations, forecast }: MapFeatureListProps) {
  return (
    <section aria-labelledby="lista-titulo" className="space-y-4">
      <h2 id="lista-titulo" className="text-lg font-semibold">Dados do mapa em lista</h2>
      <p className="text-sm">
        Os setores com risco estimado de alagamento estão em lista, com filtros e explicação, na{" "}
        <Link className="font-medium text-accent underline" href="/risk">
          página Risco de alagamento
        </Link>
        .
      </p>

      <div className="overflow-x-auto rounded-lg border border-surface-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Lista do mapa">
        <table className="w-full border-collapse bg-surface text-left text-sm">
          <caption className="bg-surface-muted px-4 py-2 text-left font-medium">Estações do INMET</caption>
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Estação</th>
              <th scope="col" className="px-4 py-2 font-medium">Situação</th>
              <th scope="col" className="px-4 py-2 font-medium">Coordenadas</th>
              <th scope="col" className="px-4 py-2 font-medium">Clima</th>
            </tr>
          </thead>
          <tbody>
            {(stations?.features ?? []).map((f) => {
              const [lon, lat] = f.geometry.coordinates;
              return (
                <tr key={f.properties.id} className="border-t border-surface-border">
                  <th scope="row" className="px-4 py-2 font-medium">
                    {f.properties.name} ({f.properties.code})
                  </th>
                  <td className="px-4 py-2">{STATION_STATUS[f.properties.status]?.label ?? f.properties.status}</td>
                  <td className="px-4 py-2 tabular-nums">{lat.toFixed(4)}, {lon.toFixed(4)}</td>
                  <td className="px-4 py-2">
                    <Link className="text-accent underline" href={weatherHref(lat, lon, f.properties.name)}>
                      Ver clima
                    </Link>
                  </td>
                </tr>
              );
            })}
            {stations && stations.features.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-2 text-ink-muted">Nenhuma estação sincronizada na região.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="overflow-x-auto rounded-lg border border-surface-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Lista do mapa">
        <table className="w-full border-collapse bg-surface text-left text-sm">
          <caption className="bg-surface-muted px-4 py-2 text-left font-medium">
            Pontos de previsão (modelo) — chuva prevista em 24 h
          </caption>
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Ponto</th>
              <th scope="col" className="px-4 py-2 font-medium">Chuva 24 h (mm)</th>
              <th scope="col" className="px-4 py-2 font-medium">Faixa</th>
              <th scope="col" className="px-4 py-2 font-medium">Temp. agora (°C)</th>
              <th scope="col" className="px-4 py-2 font-medium">Coleta</th>
            </tr>
          </thead>
          <tbody>
            {(forecast?.features ?? []).map((f) => {
              const p = f.properties;
              const [lon, lat] = f.geometry.coordinates;
              return (
                <tr key={p.point_key} className="border-t border-surface-border tabular-nums">
                  <th scope="row" className="px-4 py-2 font-medium">
                    <Link className="text-accent underline" href={weatherHref(lat, lon, "Ponto de previsão")}>
                      {lat.toFixed(4)}, {lon.toFixed(4)}
                    </Link>
                  </th>
                  <td className="px-4 py-2">
                    {formatNumber(p.precipitation_24h)}
                    {!p.precipitation_24h_complete && ` (parcial: ${p.precipitation_24h_hours} h)`}
                  </td>
                  <td className="px-4 py-2">{rainClass(p.precipitation_24h).label}</td>
                  <td className="px-4 py-2">{formatNumber(p.air_temperature_now)}</td>
                  <td className="px-4 py-2">{formatDateTime(p.issued_at)}</td>
                </tr>
              );
            })}
            {forecast && forecast.features.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-2 text-ink-muted">Nenhum ponto de previsão coletado.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
