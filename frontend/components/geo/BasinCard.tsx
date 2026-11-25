"use client";

import { RiskBadge } from "@/components/risk/RiskBadge";
import { titleCase } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import type { BasinDetail } from "@/features/geo/types";
import { formatNumber } from "@/lib/format";
import { relativeLabel } from "./TerrainSection";

const CATEGORIES: readonly string[] = ["LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"];

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-surface-border p-2">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** Ficha da bacia (FR-123): números, setores do mais grave ao menos, piscinões e drenagem. */
export function BasinCard({
  detail,
  onClose,
  onOpenBlock,
}: {
  detail: BasinDetail;
  onClose: () => void;
  onOpenBlock?: () => void;
}) {
  const b = detail.basin;
  const elevation =
    b.elev_min_m !== null && b.elev_max_m !== null
      ? `${formatNumber(b.elev_min_m, 0)}–${formatNumber(b.elev_max_m, 0)} m`
      : "—";
  return (
    <section aria-labelledby="bacia-titulo" className="space-y-4 rounded-lg border border-surface-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="bacia-titulo" className="text-lg font-semibold">
            {b.name}
          </h2>
          <p className="text-sm text-ink-muted">
            Bacia principal: {b.main_basin ?? "—"}
            {b.area_km2 !== null && ` · ${formatNumber(b.area_km2, 1)} km²`}
            {b.coverage && ` · abrangência ${b.coverage.toLowerCase()} no município`}
          </p>
        </div>
        <div className="flex gap-2">
          {onOpenBlock && (
            <button
              type="button"
              onClick={onOpenBlock}
              className="rounded-md border border-accent px-3 py-1 text-sm font-medium text-accent hover:bg-accent hover:text-white"
            >
              Ver em 3D
            </button>
          )}
          <button type="button" onClick={onClose} className="rounded-md border border-surface-border px-3 py-1 text-sm">
            Fechar
          </button>
        </div>
      </div>
      <dl className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-2">
        <Metric label="Setores de risco" value={String(b.sectors)} />
        <Metric label="Alto ou crítico agora" value={String(b.high_or_above_now)} />
        <Metric label="Ocorrências em 12 meses" value={String(b.occurrences_12m)} />
        <Metric
          label="Piscinões"
          value={
            b.reservoirs === 0
              ? "0"
              : `${b.reservoirs}${b.reservoir_volume_m3 !== null ? ` · ${formatNumber(b.reservoir_volume_m3 / 1000, 0)} mil m³` : ""}`
          }
        />
        <Metric label="Elevação" value={elevation} />
        <Metric
          label="Drenagem (aberta / fechada)"
          value={`${formatNumber(detail.drainage_km_open, 1)} / ${formatNumber(detail.drainage_km_closed, 1)} km`}
        />
      </dl>

      {detail.sectors.length > 0 && (
        <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Setores da bacia">
          <table className="w-full border-collapse text-left text-sm">
            <caption className="py-1 text-left font-medium">Setores de risco na bacia ({detail.sectors.length})</caption>
            <thead className="text-ink-muted">
              <tr>
                <th scope="col" className="py-1 pr-3 font-medium">Setor</th>
                <th scope="col" className="py-1 pr-3 font-medium">Grau</th>
                <th scope="col" className="py-1 pr-3 font-medium">Risco agora</th>
                <th scope="col" className="py-1 pr-3 font-medium">Relevo</th>
                <th scope="col" className="py-1 text-right font-medium">Córrego mais próximo</th>
              </tr>
            </thead>
            <tbody>
              {detail.sectors.slice(0, 40).map((s) => (
                <tr key={s.id} className="border-t border-surface-border">
                  <th scope="row" className="py-1 pr-3 font-medium">
                    {s.code}
                    <span className="block text-xs font-normal text-ink-muted">
                      {titleCase(s.name)} · {titleCase(s.subprefecture)}
                    </span>
                  </th>
                  <td className="py-1 pr-3">R{s.grade}</td>
                  <td className="py-1 pr-3">
                    {s.category_now && CATEGORIES.includes(s.category_now) ? (
                      <RiskBadge category={s.category_now as RiskCategory} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-1 pr-3">{relativeLabel(s.relative_elev_m)}</td>
                  <td className="py-1 text-right tabular-nums">
                    {s.nearest_drainage_m === null ? "—" : `${formatNumber(s.nearest_drainage_m, 0)} m`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {detail.sectors.length > 40 && (
            <p className="text-xs text-ink-muted">Mostrando os 40 setores de maior grau de {detail.sectors.length}.</p>
          )}
        </div>
      )}

      {detail.reservoirs.length > 0 && (
        <div>
          <h3 className="font-medium">Piscinões</h3>
          <ul className="mt-1 space-y-1 text-sm">
            {detail.reservoirs.map((r) => (
              <li key={r.id}>
                <strong>{r.name}</strong>
                {r.code && ` (${r.code})`}: {r.volume_m3 === null ? "volume não informado" : `${formatNumber(r.volume_m3, 0)} m³`}
                <span className="text-ink-muted">
                  {r.kind && ` · ${r.kind}`}
                  {r.stream && ` · córrego ${r.stream}`}
                  {r.manager && ` · gestão: ${r.manager}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-ink-muted">
        {detail.attribution}. {detail.disclaimer}
      </p>
    </section>
  );
}
