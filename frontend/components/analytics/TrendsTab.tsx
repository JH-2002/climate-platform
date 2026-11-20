"use client";

import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchTrends } from "@/features/analytics/api";
import { mm } from "@/features/analytics/format";
import { formatNumber } from "@/lib/format";
import { ChartFrame } from "./ChartFrame";

/** Aba Tendências (FR-091, AC-088): série medida de 1933 a 2025, sem afirmar causa. */
export function TrendsTab() {
  const trends = useQuery({ queryKey: ["analytics", "trends"], queryFn: ({ signal }) => fetchTrends(signal) });
  if (trends.isPending) {
    return (
      <div role="status" className="h-60 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
        <span className="sr-only">Carregando a série histórica…</span>
      </div>
    );
  }
  if (trends.isError) {
    return <p role="alert" className="text-sm">Não foi possível carregar a série histórica. {trends.error.message}</p>;
  }
  const data = trends.data;
  if (data.annual.length === 0) {
    return <p className="text-sm text-ink-muted">A série do IAG/USP ainda não foi importada.</p>;
  }
  const avg = new Map(data.moving_average_10y.map((p) => [p.year, p.value]));
  const rows = data.annual.map((p) => ({ ano: p.year, total: p.value, media10: avg.get(p.year) ?? null }));
  const first = data.annual[0]!.year;
  const last = data.annual[data.annual.length - 1]!.year;

  return (
    <div className="space-y-5">
      <aside role="note" className="rounded-lg border-l-4 border-accent bg-surface p-3 text-sm">
        {data.note}
      </aside>
      <ChartFrame
        id="serie-iag"
        title={`Chuva anual medida no IAG/USP (Água Funda), ${first}–${last}`}
        summary="Linha fina: total de cada ano; linha grossa: média dos 10 anos anteriores (inclusive). A média móvel suaviza a variabilidade de ano para ano."
        kind="OBSERVED"
        source={data.attribution}
        rows={rows}
        columns={[
          { key: "ano", label: "Ano" },
          { key: "total", label: "Total anual", format: mm },
          { key: "media10", label: "Média de 10 anos", format: mm },
        ]}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
            <XAxis dataKey="ano" tick={{ fontSize: 11 }} interval={9} />
            <YAxis tickFormatter={(v: number) => formatNumber(v, 0)} tick={{ fontSize: 12 }} width={52} unit=" mm" />
            <Tooltip formatter={(v) => mm(Number(v))} />
            <Legend />
            <Line dataKey="total" name="Total anual" stroke="#7fb3c9" dot={false} />
            <Line dataKey="media10" name="Média de 10 anos" stroke="#1d4f91" strokeWidth={3} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>

      <section aria-labelledby="normais" className="space-y-2 rounded-lg border border-surface-border bg-surface p-4 text-sm">
        <h3 id="normais" className="font-semibold">Normais climatológicas (médias de 30 anos)</h3>
        <table className="w-full max-w-xl border-collapse text-left">
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="py-1 pr-4 font-medium">Período</th>
              <th scope="col" className="py-1 pr-4 font-medium">Calculada pelo sistema</th>
              <th scope="col" className="py-1 pr-4 font-medium">Publicada pela Prefeitura</th>
              <th scope="col" className="py-1 font-medium">Diferença</th>
            </tr>
          </thead>
          <tbody>
            {data.normals.map((n) => (
              <tr key={n.period} className="border-t border-surface-border tabular-nums">
                <th scope="row" className="py-1 pr-4 font-normal">{n.period.replace("-", "–")}</th>
                <td className="py-1 pr-4">{mm(n.computed)}</td>
                <td className="py-1 pr-4">{mm(n.published)}</td>
                <td className="py-1">{mm(n.difference)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-ink-muted">
          A conferência mostra que a série importada reproduz as normais oficiais. A diferença entre
          normais descreve a série; não indica, sozinha, a causa.
        </p>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { id: "chuvosos", title: "Anos mais chuvosos", items: data.wettest },
          { id: "secos", title: "Anos mais secos", items: data.driest },
        ].map((group) => (
          <section key={group.id} aria-labelledby={group.id} className="space-y-1 rounded-lg border border-surface-border bg-surface p-4 text-sm">
            <h3 id={group.id} className="font-semibold">{group.title}</h3>
            <ol className="list-inside list-decimal tabular-nums">
              {group.items.map((y) => (
                <li key={y.year}>
                  {y.year}: {mm(y.value)}
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
