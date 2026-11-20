"use client";

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchDescribe, fetchRanking, fetchSeries, seriesCsvUrl, studioSeriesParams } from "@/features/analytics/api";
import { num, periodLabel } from "@/features/analytics/format";
import { kindLabel } from "@/features/analytics/kinds";
import {
  AGG_LABELS,
  COMPARE_LABELS,
  GRAIN_LABELS,
  VIZ_LABELS,
  compatibleComparisons,
  compatibleVisualizations,
  equalBins,
  switchDataset,
  type StudioState,
  type Viz,
} from "@/features/analytics/studio";
import type { DatasetInfo, DescribeResult, SeriesResponse } from "@/features/analytics/types";
import { titleCase } from "@/features/risk/categories";

interface StudioTabProps {
  datasets: DatasetInfo[];
  state: StudioState;
  today: string;
  onChange: (state: StudioState) => void;
}

const SERIES_VIZ: readonly Viz[] = ["line", "bar", "area", "table", "calendar", "histogram"];

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

const input = "rounded-md border border-surface-border bg-surface px-2 py-1.5";

function locationLabel(dataset: DatasetInfo, key: string | null): string {
  const found = dataset.locations.find((l) => l.key === key);
  return found ? found.label : titleCase(key);
}

function SeriesTable({ series }: { series: SeriesResponse }) {
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-surface-border">
      <table className="w-full border-collapse bg-surface text-left text-xs">
        <caption className="sr-only">
          {series.variable_label} — {series.dataset_name}
        </caption>
        <thead className="sticky top-0 bg-surface text-ink-muted">
          <tr>
            <th scope="col" className="px-3 py-1 font-medium">Período</th>
            <th scope="col" className="px-3 py-1 font-medium">Valor ({series.unit})</th>
            {series.reference_label && <th scope="col" className="px-3 py-1 font-medium">{series.reference_label}</th>}
            <th scope="col" className="px-3 py-1 font-medium">Cobertura</th>
          </tr>
        </thead>
        <tbody>
          {series.points.map((p) => (
            <tr key={p.start} className="border-t border-surface-border tabular-nums">
              <th scope="row" className="px-3 py-1 font-normal">{periodLabel(p.start, series.grain)}</th>
              <td className="px-3 py-1">{p.insufficient ? "dados insuficientes" : num(p.value, 2)}</td>
              {series.reference_label && <td className="px-3 py-1">{num(p.reference, 2)}</td>}
              <td className="px-3 py-1">
                {p.expected ? `${p.n} de ${p.expected}` : p.n}
                {p.partial ? " (parcial)" : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Calendar({ series }: { series: SeriesResponse }) {
  const values = series.points.map((p) => p.value).filter((v): v is number => v !== null);
  const max = Math.max(1, ...values);
  const byMonth = new Map<string, typeof series.points>();
  for (const p of series.points) {
    const key = p.start.slice(0, 7);
    byMonth.set(key, [...(byMonth.get(key) ?? []), p]);
  }
  return (
    <div className="space-y-1 overflow-x-auto" aria-hidden="true">
      {[...byMonth.entries()].map(([month, days]) => (
        <div key={month} className="flex items-center gap-1">
          <span className="w-16 shrink-0 text-xs text-ink-muted">{periodLabel(`${month}-01`, "month")}</span>
          {days.map((d) => (
            <span
              key={d.start}
              title={`${periodLabel(d.start, "day")}: ${num(d.value)} ${series.unit}`}
              className="inline-block h-4 w-4 rounded-sm border border-surface-border"
              style={{ backgroundColor: d.value === null ? "#f5f7f9" : `rgba(29, 79, 145, ${0.1 + 0.9 * (d.value / max)})` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function BoxView({ d }: { d: DescribeResult }) {
  if (d.minimum === null || d.maximum === null || d.p25 === null || d.p75 === null || d.median === null) {
    return <p className="text-sm text-ink-muted">Sem valores no período.</p>;
  }
  const span = d.maximum - d.minimum || 1;
  const x = (v: number) => 20 + ((v - d.minimum!) / span) * 560;
  return (
    <svg viewBox="0 0 600 90" className="h-28 w-full" aria-hidden="true">
      <line x1={x(d.minimum)} x2={x(d.maximum)} y1={45} y2={45} stroke="#4d5d6b" />
      <rect x={x(d.p25)} y={25} width={x(d.p75) - x(d.p25)} height={40} fill="#7fb3c9" stroke="#1d4f91" />
      <line x1={x(d.median)} x2={x(d.median)} y1={25} y2={65} stroke="#14202b" strokeWidth={3} />
      <text x={x(d.minimum)} y={85} fontSize={11} textAnchor="start">{num(d.minimum)}</text>
      <text x={x(d.maximum)} y={85} fontSize={11} textAnchor="end">{num(d.maximum)}</text>
    </svg>
  );
}

/** Analytics Studio (FR-094): consulta montada pelo usuário, com visualizações compatíveis. */
export function StudioTab({ datasets, state, today, onChange }: StudioTabProps) {
  const dataset = datasets.find((d) => d.id === state.dataset)!;
  const variable = dataset.variables.find((v) => v.code === state.variable) ?? dataset.variables[0]!;
  const vizOptions = compatibleVisualizations(dataset, state.grain);
  const compareOptions = compatibleComparisons(dataset, state.grain);
  const params = studioSeriesParams(state);
  const usesSeries = SERIES_VIZ.includes(state.viz);

  const series = useQuery({
    queryKey: ["analytics", "studio-series", params],
    queryFn: ({ signal }) => fetchSeries(params, signal),
    enabled: usesSeries,
  });
  const describe = useQuery({
    queryKey: ["analytics", "studio-describe", state.dataset, state.variable, state.location, state.start, state.end],
    queryFn: ({ signal }) => fetchDescribe(state.dataset, state.variable, state.location, state.start, state.end, signal),
    enabled: state.viz === "box",
  });
  const ranking = useQuery({
    queryKey: ["analytics", "studio-ranking", state.dataset, state.variable, state.agg, state.start, state.end],
    queryFn: ({ signal }) => fetchRanking(state.dataset, state.variable, state.agg, state.start, state.end, signal),
    enabled: state.viz === "ranking",
  });

  const set = (patch: Partial<StudioState>) => {
    const next = { ...state, ...patch };
    const vizNow = compatibleVisualizations(dataset, next.grain);
    if (!vizNow.includes(next.viz)) next.viz = vizNow[0] ?? "table";
    if (!compatibleComparisons(dataset, next.grain).includes(next.compare ?? "")) next.compare = null;
    onChange(next);
  };

  const rows = (series.data?.points ?? []).map((p) => ({
    periodo: periodLabel(p.start, state.grain),
    valor: p.value,
    referencia: p.reference,
  }));
  const histogram = equalBins(
    (series.data?.points ?? []).map((p) => p.value).filter((v): v is number => v !== null),
  ).map((b) => ({ faixa: `${num(b.low)}–${num(b.high)}`, n: b.n }));
  const error = series.error ?? describe.error ?? ranking.error;

  return (
    <div className="space-y-4">
      <form className="grid gap-3 rounded-lg border border-surface-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e) => e.preventDefault()}>
        <Field label="Conjunto de dados">
          <select className={input} value={state.dataset} onChange={(e) => onChange(switchDataset(datasets.find((d) => d.id === e.target.value)!, today))}>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Variável">
          <select className={input} value={state.variable} onChange={(e) => {
            const v = dataset.variables.find((x) => x.code === e.target.value)!;
            set({ variable: v.code, agg: v.aggregations.includes(state.agg) ? state.agg : v.aggregations[0]! });
          }}>
            {dataset.variables.map((v) => (
              <option key={v.code} value={v.code}>{v.label} ({v.unit})</option>
            ))}
          </select>
        </Field>
        {dataset.locations.length > 0 && (
          <Field label="Local">
            <select className={input} value={state.location ?? ""} onChange={(e) => set({ location: e.target.value || null })}>
              {dataset.id === "flood-occurrences" || dataset.id === "ingestion-runs" ? <option value="">Todos</option> : null}
              {dataset.locations.map((l) => (
                <option key={l.key} value={l.key}>{l.label}</option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Início">
          <input type="date" className={input} value={state.start} max={state.end} onChange={(e) => e.target.value && set({ start: e.target.value })} />
        </Field>
        <Field label="Fim">
          <input type="date" className={input} value={state.end} min={state.start} onChange={(e) => e.target.value && set({ end: e.target.value })} />
        </Field>
        <Field label="Agrupar por">
          <select className={input} value={state.grain} onChange={(e) => set({ grain: e.target.value })}>
            {dataset.grains.map((g) => (
              <option key={g} value={g}>{GRAIN_LABELS[g] ?? g}</option>
            ))}
          </select>
        </Field>
        <Field label="Agregação">
          <select className={input} value={state.agg} onChange={(e) => set({ agg: e.target.value })}>
            {variable.aggregations.map((a) => (
              <option key={a} value={a}>{AGG_LABELS[a] ?? a}</option>
            ))}
          </select>
        </Field>
        <Field label="Comparar com">
          <select className={input} value={state.compare ?? ""} onChange={(e) => set({ compare: e.target.value || null })}>
            <option value="">Nada</option>
            {compareOptions.map((c) => (
              <option key={c} value={c}>{COMPARE_LABELS[c]}</option>
            ))}
          </select>
        </Field>
        <fieldset className="sm:col-span-2 lg:col-span-4">
          <legend className="text-xs text-ink-muted">Visualização (só as adequadas a este conjunto)</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            {vizOptions.map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={state.viz === v}
                onClick={() => set({ viz: v })}
                className={`rounded-md border px-3 py-1 text-sm ${state.viz === v ? "border-accent bg-accent text-white" : "border-surface-border hover:bg-surface-muted"}`}
              >
                {VIZ_LABELS[v]}
              </button>
            ))}
          </div>
        </fieldset>
      </form>

      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
        <span className="rounded border border-surface-border px-1.5 py-0.5 font-medium text-ink">{kindLabel(dataset.kind)}</span>
        <span>{dataset.attribution ?? dataset.source_name}</span>
        {state.location && <span>· {locationLabel(dataset, state.location)}</span>}
        {usesSeries && (
          <a className="ml-auto rounded-md border border-accent px-3 py-1 font-medium text-accent hover:bg-accent hover:text-white" href={seriesCsvUrl(params)} download>
            Exportar CSV
          </a>
        )}
      </div>
      {dataset.caveats.map((c) => (
        <p key={c} className="text-xs text-ink-muted">{c}</p>
      ))}

      {error && (
        <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
          {error.message}
        </p>
      )}

      {usesSeries && series.data && (
        <section aria-label="Resultado" className="space-y-3">
          {state.viz !== "table" && (
            <div className="h-80 rounded-lg border border-surface-border bg-surface p-2" role="img" aria-label={`${series.data.variable_label} (${series.data.unit}) por ${GRAIN_LABELS[state.grain]?.toLowerCase()}. Os dados estão na tabela abaixo.`}>
              {state.viz === "calendar" ? (
                <Calendar series={series.data} />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  {state.viz === "histogram" ? (
                    <BarChart data={histogram}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
                      <XAxis dataKey="faixa" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 12 }} width={44} />
                      <Tooltip />
                      <Bar dataKey="n" name="Quantidade de períodos" fill="#1d4f91" />
                    </BarChart>
                  ) : state.viz === "area" ? (
                    <AreaChart data={rows}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
                      <XAxis dataKey="periodo" tick={{ fontSize: 11 }} minTickGap={24} />
                      <YAxis tick={{ fontSize: 12 }} width={52} />
                      <Tooltip />
                      <Area dataKey="valor" name={series.data.variable_label} stroke="#1d4f91" fill="#7fb3c9" />
                    </AreaChart>
                  ) : (
                    <ComposedChart data={rows}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
                      <XAxis dataKey="periodo" tick={{ fontSize: 11 }} minTickGap={24} />
                      <YAxis tick={{ fontSize: 12 }} width={52} />
                      <Tooltip />
                      <Legend />
                      {state.viz === "bar" ? (
                        <Bar dataKey="valor" name={series.data.variable_label} fill="#3a86b4" />
                      ) : (
                        <Line dataKey="valor" name={series.data.variable_label} stroke="#1d4f91" dot={false} />
                      )}
                      {series.data.reference_label && (
                        <Line dataKey="referencia" name={series.data.reference_label} stroke="#14202b" strokeDasharray="4 3" dot={false} />
                      )}
                    </ComposedChart>
                  )}
                </ResponsiveContainer>
              )}
            </div>
          )}
          <SeriesTable series={series.data} />
        </section>
      )}

      {state.viz === "box" && describe.data && (
        <section aria-label="Resumo estatístico" className="space-y-2 rounded-lg border border-surface-border bg-surface p-4 text-sm">
          <BoxView d={describe.data} />
          <p>
            Mediana {num(describe.data.median)} · quartis {num(describe.data.p25)} e {num(describe.data.p75)} · mínimo{" "}
            {num(describe.data.minimum)} · máximo {num(describe.data.maximum)} {describe.data.unit} · {describe.data.n} valores,{" "}
            {describe.data.missing} ausentes · {describe.data.outlier_count} atípicos.
          </p>
          <p className="text-xs text-ink-muted">{describe.data.method}</p>
        </section>
      )}

      {state.viz === "ranking" && ranking.data && (
        <section aria-label="Ranking" className="rounded-lg border border-surface-border bg-surface p-4 text-sm">
          <ol className="list-inside list-decimal tabular-nums">
            {ranking.data.items.map((item) => (
              <li key={item.key}>
                {locationLabel(dataset, item.key)}: {num(item.value)} {ranking.data.unit}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
