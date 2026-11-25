import { COLUMN_MAX_M, RAIN_CLASSES, STATION_STATUS } from "@/features/map/geometry";
import type { MapMode } from "@/features/map/state";
import { OFFICIAL_COLORS } from "@/components/alerts/mapColors";
import { RiskSwatch } from "@/components/risk/RiskBadge";
import { CATEGORIES, CATEGORY_ORDER } from "@/features/risk/categories";

/** Legenda com cor e texto (FR-056): a informação nunca depende só da cor. */
export function MapLegend({ mode }: { mode: MapMode }) {
  return (
    <section aria-labelledby="legenda-titulo" className="space-y-3 rounded-lg border border-surface-border bg-surface p-4 text-sm">
      <h2 id="legenda-titulo" className="font-semibold">Legenda</h2>
      <div>
        <h3 className="text-xs font-medium text-ink-muted">Estações do INMET</h3>
        <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
          {(["OPERATIONAL", "FAULT", "INACTIVE"] as const).map((s) => (
            <li key={s} className="flex items-center gap-2">
              <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full border-2 border-white shadow" style={{ backgroundColor: STATION_STATUS[s]!.color }} />
              {STATION_STATUS[s]!.label}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="text-xs font-medium text-ink-muted">
          Chuva prevista em 24 h (modelo){" "}
          {mode === "3d" ? `— altura da coluna proporcional à chuva (até ${COLUMN_MAX_M / 1000} km)` : "— tamanho do círculo proporcional à chuva"}
        </h3>
        <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
          {RAIN_CLASSES.map((c) => (
            <li key={c.id} className="flex items-center gap-2">
              <span aria-hidden="true" className="inline-block h-3 w-5 rounded-sm" style={{ backgroundColor: c.color }} />
              {c.label}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-xs text-ink-muted">Faixas visuais, não são alertas oficiais.</p>
      </div>
      <div>
        <h3 className="text-xs font-medium text-ink-muted">
          Risco estimado de alagamento por setor (experimental)
          {mode === "3d" ? " — altura do bloco cresce com a categoria" : ""}
        </h3>
        <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
          {CATEGORY_ORDER.map((c) => (
            <li key={c} className="flex items-center gap-2">
              <RiskSwatch category={c} />
              {CATEGORIES[c].label}
            </li>
          ))}
          <li className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full border border-white bg-gray-800" />
            Ocorrência registrada (12 meses)
          </li>
        </ul>
        <p className="mt-1 text-xs text-ink-muted">
          Setores de risco hidrológico do GeoSampa × chuva prevista. Estimativa do sistema, não
          aviso oficial; detalhes na página Risco de alagamento.
        </p>
      </div>
      <div>
        <h3 className="text-xs font-medium text-ink-muted">Alertas oficiais vigentes e próximos (camada desligada por padrão)</h3>
        <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
          <li className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block h-3 w-5 rounded-sm border-2" style={{ borderColor: OFFICIAL_COLORS.CIVIL_DEFENSE }} />
            Defesa Civil
          </li>
          <li className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block h-3 w-5 rounded-sm border-2" style={{ borderColor: OFFICIAL_COLORS.WEATHER_WARNING }} />
            INMET
          </li>
        </ul>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full border-[3px] border-accent bg-white" />
          Meus locais
        </span>
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dashed border-accent" />
          Região de interesse
        </span>
      </div>
    </section>
  );
}
