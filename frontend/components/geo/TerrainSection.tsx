"use client";

import { useSectorTerrain } from "@/features/geo/hooks";
import { formatNumber } from "@/lib/format";

/** Relevo relativo em palavras: o número sozinho não diz se é vale ou encosta. */
export function relativeLabel(m: number | null): string {
  if (m === null) return "sem dado";
  if (m <= -5) return `${formatNumber(Math.abs(m), 0)} m abaixo do entorno (fundo de vale)`;
  if (m >= 5) return `${formatNumber(m, 0)} m acima do entorno (parte alta)`;
  return "no nível do entorno";
}

/**
 * Seção "Terreno" da explicação do setor (FR-127). Informativa: não muda a categoria (BR-121).
 */
export function TerrainSection({ sectorId }: { sectorId: number }) {
  const terrain = useSectorTerrain(sectorId);
  if (terrain.isPending) return <p className="text-sm text-ink-muted">Carregando o terreno…</p>;
  if (terrain.isError) {
    return (
      <p className="text-sm text-ink-muted">
        Terreno ainda não calculado para este setor (aguarda a hidrografia e o relevo).
      </p>
    );
  }
  const t = terrain.data;
  const drainage = t.nearest_drainage;
  return (
    <section aria-labelledby={`terreno-${sectorId}`} className="space-y-2 rounded-md bg-surface-muted p-3 text-sm">
      <h3 id={`terreno-${sectorId}`} className="font-medium">
        Terreno
      </h3>
      <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-ink-muted">Elevação (mediana)</dt>
          <dd>{t.elev_median_m === null ? "—" : `${formatNumber(t.elev_median_m, 0)} m`}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Em relação ao entorno de 1 km</dt>
          <dd>{relativeLabel(t.relative_elev_m)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Declividade média</dt>
          <dd>{t.slope_mean_pct === null ? "—" : `${formatNumber(t.slope_mean_pct, 0)}%`}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Bacia</dt>
          <dd>
            {t.basin_name ?? "fora das bacias mapeadas"}
            {t.main_basin && <span className="text-ink-muted"> ({t.main_basin})</span>}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-ink-muted">Curso d’água mais próximo</dt>
          <dd>
            {drainage
              ? `${drainage.name ?? "trecho sem nome"} a ${formatNumber(drainage.distance_m, 0)} m — ${drainage.course_type.toLowerCase()}`
              : "—"}
          </dd>
        </div>
      </dl>
      {t.low_sample && t.cells > 0 && (
        <p className="text-xs text-amber-900">
          Setor pequeno: só {t.cells} célula(s) do relevo de 30 m. Os números de elevação são frágeis.
        </p>
      )}
      <p className="text-xs text-ink-muted">
        {t.disclaimer} Fontes: Copernicus DEM GLO-30
        {t.dem_resolution_m !== null && ` (~${formatNumber(t.dem_resolution_m, 0)} m)`}; {t.hydro_attribution}.
      </p>
    </section>
  );
}
