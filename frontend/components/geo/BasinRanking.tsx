"use client";

import { SORT_LABELS } from "@/features/geo/state";
import type { BasinList, BasinSort } from "@/features/geo/types";
import { formatNumber } from "@/lib/format";

interface Props {
  list: BasinList;
  sort: BasinSort;
  selectedId: number | null;
  onSort: (sort: BasinSort) => void;
  onSelect: (id: number) => void;
  limit?: number;
}

/** Ranking de bacias (FR-123): setores, risco agora, ocorrências e piscinões. */
export function BasinRanking({ list, sort, selectedId, onSort, onSelect, limit = 30 }: Props) {
  const items = list.items.slice(0, limit);
  return (
    <section aria-labelledby="bacias-titulo" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="bacias-titulo" className="text-lg font-semibold">
            Bacias hidrográficas
          </h2>
          <p className="text-sm text-ink-muted">
            {list.total_sectors} setores de risco em {list.items.filter((b) => b.sectors > 0).length} bacias
            {list.sectors_outside_basins > 0 && `; ${list.sectors_outside_basins} fora das bacias mapeadas`}. Ocorrências
            desde {list.occurrences_since.split("-").reverse().join("/")}.
          </p>
        </div>
        <label className="flex flex-col gap-1 text-xs text-ink-muted">
          Ordenar por
          <select
            className="rounded-md border border-surface-border bg-surface px-2 py-1.5 text-sm text-ink"
            value={sort}
            onChange={(e) => onSort(e.target.value as BasinSort)}
          >
            {(Object.keys(SORT_LABELS) as BasinSort[]).map((s) => (
              <option key={s} value={s}>
                {SORT_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="overflow-x-auto rounded-lg border border-surface-border">
        <table className="w-full border-collapse bg-surface text-left text-sm">
          <caption className="sr-only">Bacias hidrográficas ordenadas por {SORT_LABELS[sort].toLowerCase()}</caption>
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Bacia</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Setores</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Alto ou crítico agora</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Ocorrências 12 meses</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Piscinões</th>
              <th scope="col" className="px-3 py-2 font-medium">
                <span className="sr-only">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((b) => (
              <tr key={b.id} className={`border-t border-surface-border ${selectedId === b.id ? "bg-surface-muted" : ""}`}>
                <th scope="row" className="px-3 py-2 font-medium">
                  {b.name}
                  <span className="block text-xs font-normal text-ink-muted">
                    {b.main_basin ?? "—"}
                    {b.area_km2 !== null && ` · ${formatNumber(b.area_km2, 1)} km²`}
                  </span>
                </th>
                <td className="px-3 py-2 text-right tabular-nums">
                  {b.sectors}
                  {b.sectors > 0 && (
                    <span className="block text-xs text-ink-muted">R4 {b.sectors_by_grade.R4} · R3 {b.sectors_by_grade.R3}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{b.high_or_above_now}</td>
                <td className="px-3 py-2 text-right tabular-nums">{b.occurrences_12m}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {b.reservoirs}
                  {b.reservoir_volume_m3 !== null && b.reservoirs > 0 && (
                    <span className="block text-xs text-ink-muted">{formatNumber(b.reservoir_volume_m3 / 1000, 0)} mil m³</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => onSelect(b.id)}
                    aria-label={`Ver a ficha da bacia ${b.name}`}
                    className="rounded-md border border-accent px-2 py-1 text-xs font-medium text-accent hover:bg-accent hover:text-white"
                  >
                    Ficha
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {list.items.length > limit && (
        <p className="text-xs text-ink-muted">
          Mostrando {limit} de {list.items.length} bacias. Mude a ordenação para ver outras.
        </p>
      )}
      <p className="text-xs text-ink-muted">{list.attribution}. O risco “agora” é a estimativa experimental mais recente.</p>
    </section>
  );
}
