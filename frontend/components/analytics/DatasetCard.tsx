"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { fetchDescribe } from "@/features/analytics/api";
import { num, pct } from "@/features/analytics/format";
import { kindLabel } from "@/features/analytics/kinds";
import type { DatasetInfo } from "@/features/analytics/types";
import { FRESHNESS_LABELS } from "@/features/sources/types";

function periodBounds(dataset: DatasetInfo): { start: string; end: string } | null {
  if (!dataset.period_start || !dataset.period_end) return null;
  const start = dataset.period_start.length === 7 ? `${dataset.period_start}-01` : dataset.period_start.slice(0, 10);
  const end = dataset.period_end.length === 7 ? `${dataset.period_end}-28` : dataset.period_end.slice(0, 10);
  return { start, end };
}

/** Ficha de um conjunto (FR-082, FR-083, FR-095): metadados e estatísticas descritivas. */
export function DatasetCard({ dataset }: { dataset: DatasetInfo }) {
  const [variable, setVariable] = useState(dataset.variables[0]?.code ?? "");
  const [location, setLocation] = useState<string | null>(dataset.locations[0]?.key ?? null);
  const bounds = periodBounds(dataset);
  const stats = useQuery({
    queryKey: ["analytics", "describe", dataset.id, variable, location, bounds?.start, bounds?.end],
    queryFn: ({ signal }) => fetchDescribe(dataset.id, variable, location, bounds!.start, bounds!.end, signal),
    enabled: dataset.numeric && bounds !== null && dataset.records > 0,
  });
  const unit = dataset.variables.find((v) => v.code === variable)?.unit ?? "";
  const studio = new URLSearchParams({ aba: "studio", conjunto: dataset.id });
  const freshness = dataset.freshness ? ((FRESHNESS_LABELS as Record<string, string>)[dataset.freshness] ?? dataset.freshness) : "—";

  return (
    <article aria-labelledby={`ds-${dataset.id}`} className="space-y-3 rounded-lg border border-surface-border bg-surface p-4 text-sm">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id={`ds-${dataset.id}`} className="font-semibold">{dataset.name}</h2>
          <p className="text-ink-muted">{dataset.description}</p>
        </div>
        <span className="rounded border border-surface-border px-1.5 py-0.5 text-xs font-medium">{kindLabel(dataset.kind)}</span>
      </header>
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        <div><dt className="inline text-ink-muted">Fonte: </dt><dd className="inline">{dataset.source_name ?? "—"}</dd></div>
        <div><dt className="inline text-ink-muted">Frescor: </dt><dd className="inline">{freshness}</dd></div>
        <div><dt className="inline text-ink-muted">Período: </dt><dd className="inline">{dataset.period_start ?? "—"} a {dataset.period_end ?? "—"}</dd></div>
        <div><dt className="inline text-ink-muted">Registros: </dt><dd className="inline tabular-nums">{dataset.records.toLocaleString("pt-BR")}</dd></div>
        <div><dt className="inline text-ink-muted">Cobertura: </dt><dd className="inline">{dataset.spatial}</dd></div>
        <div><dt className="inline text-ink-muted">Licença: </dt><dd className="inline">{dataset.license ?? "—"}</dd></div>
      </dl>
      {dataset.attribution && <p className="text-xs text-ink-muted">Atribuição: {dataset.attribution}</p>}
      <div>
        <h3 className="text-xs font-medium text-ink-muted">Variáveis</h3>
        <ul className="list-inside list-disc">
          {dataset.variables.map((v) => (
            <li key={v.code}>{v.label} ({v.unit})</li>
          ))}
        </ul>
      </div>
      {dataset.caveats.map((c) => (
        <p key={c} className="text-xs text-ink-muted">{c}</p>
      ))}

      {dataset.numeric && dataset.records > 0 && (
        <div className="space-y-2 border-t border-surface-border pt-3">
          <h3 className="font-medium">Estatísticas do período completo</h3>
          <div className="flex flex-wrap gap-3">
            {dataset.variables.length > 1 && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-ink-muted">Variável</span>
                <select className="rounded-md border border-surface-border px-2 py-1 text-sm" value={variable} onChange={(e) => setVariable(e.target.value)}>
                  {dataset.variables.map((v) => (
                    <option key={v.code} value={v.code}>{v.label}</option>
                  ))}
                </select>
              </label>
            )}
            {dataset.locations.length > 1 && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-ink-muted">Local</span>
                <select className="rounded-md border border-surface-border px-2 py-1 text-sm" value={location ?? ""} onChange={(e) => setLocation(e.target.value)}>
                  {dataset.locations.map((l) => (
                    <option key={l.key} value={l.key}>{l.label}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {stats.isPending && <p className="text-ink-muted">Calculando…</p>}
          {stats.isError && <p role="alert">{stats.error.message}</p>}
          {stats.data && (
            <table className="w-full max-w-xl border-collapse text-left text-xs tabular-nums">
              <caption className="sr-only">Estatísticas descritivas</caption>
              <tbody>
                {[
                  ["Valores", `${stats.data.n.toLocaleString("pt-BR")} de ${stats.data.expected.toLocaleString("pt-BR")} (${pct(stats.data.coverage, 1)})`],
                  ["Ausentes", stats.data.missing.toLocaleString("pt-BR")],
                  ["Média", `${num(stats.data.mean, 2)} ${unit}`],
                  ["Mediana", `${num(stats.data.median, 2)} ${unit}`],
                  ["Desvio padrão", `${num(stats.data.std, 2)} ${unit}`],
                  ["Mínimo / máximo", `${num(stats.data.minimum, 1)} / ${num(stats.data.maximum, 1)} ${unit}`],
                  ["Percentis 5 / 25 / 75 / 95", `${num(stats.data.p5)} / ${num(stats.data.p25)} / ${num(stats.data.p75)} / ${num(stats.data.p95)} ${unit}`],
                  ["Valores atípicos (1,5 × IQR)", `${stats.data.outlier_count} (maiores: ${stats.data.outliers.slice(0, 5).map((v) => num(v)).join("; ") || "—"})`],
                ].map(([label, value]) => (
                  <tr key={label} className="border-t border-surface-border">
                    <th scope="row" className="py-1 pr-4 font-normal text-ink-muted">{label}</th>
                    <td className="py-1">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      <Link className="inline-block font-medium text-accent underline" href={`/analytics?${studio}`}>
        Explorar no Studio
      </Link>
    </article>
  );
}
