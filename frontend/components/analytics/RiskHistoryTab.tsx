"use client";

import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RiskSwatch } from "@/components/risk/RiskBadge";
import { fetchRiskHistory } from "@/features/analytics/api";
import { CATEGORIES, CATEGORY_ORDER, titleCase } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import { formatDateTime } from "@/lib/format";
import { ChartFrame } from "./ChartFrame";

function GroupTable({ id, title, groups }: { id: string; title: string; groups: { name: string; counts: Record<string, number>; total: number }[] }) {
  return (
    <section aria-labelledby={id} className="space-y-2 rounded-lg border border-surface-border bg-surface p-4 text-sm">
      <h3 id={id} className="font-semibold">{title}</h3>
      <div className="max-h-96 overflow-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-surface text-ink-muted">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">Nome</th>
              {CATEGORY_ORDER.map((c) => (
                <th key={c} scope="col" className="py-1 pr-3 font-medium">
                  <span className="inline-flex items-center gap-1">
                    <RiskSwatch category={c} />
                    {CATEGORIES[c].label}
                  </span>
                </th>
              ))}
              <th scope="col" className="py-1 font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.name} className="border-t border-surface-border tabular-nums">
                <th scope="row" className="py-1 pr-3 font-normal">{titleCase(g.name)}</th>
                {CATEGORY_ORDER.map((c) => (
                  <td key={c} className="py-1 pr-3">{g.counts[c] ?? 0}</td>
                ))}
                <td className="py-1">{g.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Aba Risco (FR-092): evolução por execução e distribuição na última estimativa. */
export function RiskHistoryTab() {
  const history = useQuery({ queryKey: ["analytics", "risk-history"], queryFn: ({ signal }) => fetchRiskHistory(signal) });
  if (history.isPending) {
    return (
      <div role="status" className="h-60 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
        <span className="sr-only">Carregando o histórico do risco…</span>
      </div>
    );
  }
  if (history.isError) return <p role="alert" className="text-sm">{history.error.message}</p>;
  const data = history.data;
  const rows = data.runs.map((r) => ({ quando: formatDateTime(r.computed_at).slice(0, 17), ...r.counts }));
  const order: RiskCategory[] = ["UNKNOWN", "LOW", "MODERATE", "HIGH", "CRITICAL"];
  return (
    <div className="space-y-5">
      <aside role="note" className="rounded-lg border-l-4 border-status-warn bg-amber-50 p-3 text-sm">
        {data.engine_note} Em emergência, ligue 199 (Defesa Civil).
      </aside>
      <ChartFrame
        id="risco-evolucao"
        title="Setores por categoria em cada execução (últimos 7 dias)"
        summary={`${data.runs.length} execuções horárias do motor v0. Cada faixa mostra quantos dos setores mapeados ficaram em cada categoria.`}
        kind="DERIVED"
        source="Motor de risco v0 (experimental): GeoSampa × previsão Open-Meteo"
        rows={rows}
        columns={[{ key: "quando", label: "Execução" }, ...CATEGORY_ORDER.map((c) => ({ key: c, label: CATEGORIES[c].label }))]}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
            <XAxis dataKey="quando" tick={{ fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fontSize: 12 }} width={44} />
            <Tooltip />
            <Legend />
            {order.map((c) => (
              <Area key={c} dataKey={c} name={CATEGORIES[c].label} stackId="1" stroke={CATEGORIES[c].color} fill={CATEGORIES[c].color} fillOpacity={0.7} />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>
      <div className="grid gap-4 lg:grid-cols-2">
        <GroupTable id="por-subprefeitura" title="Última estimativa por subprefeitura" groups={data.by_subprefecture} />
        <GroupTable id="por-bacia" title="Última estimativa por bacia" groups={data.by_basin} />
      </div>
    </div>
  );
}
