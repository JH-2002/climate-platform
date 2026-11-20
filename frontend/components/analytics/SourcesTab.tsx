"use client";

import { useQuery } from "@tanstack/react-query";
import { StatusBadge, type BadgeTone } from "@/components/ui/StatusBadge";
import { fetchSourcesHealth } from "@/features/analytics/api";
import { num, pct } from "@/features/analytics/format";
import { FRESHNESS_LABELS, REASON_LABELS } from "@/features/sources/types";
import { formatDateTime } from "@/lib/format";

const TONES: Record<string, BadgeTone> = {
  FRESH: "ok",
  DELAYED: "warn",
  STALE: "error",
  UNAVAILABLE: "error",
  UNKNOWN: "unknown",
};

/** Aba Fontes e dados (FR-093): disponibilidade, atraso, falhas, rejeições e cobertura. */
export function SourcesTab() {
  const health = useQuery({
    queryKey: ["analytics", "sources-health"],
    queryFn: ({ signal }) => fetchSourcesHealth(signal),
    refetchInterval: 60_000,
  });
  if (health.isPending) {
    return (
      <div role="status" className="h-60 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
        <span className="sr-only">Carregando a saúde das fontes…</span>
      </div>
    );
  }
  if (health.isError) return <p role="alert" className="text-sm">{health.error.message}</p>;
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-surface-border">
        <table className="w-full border-collapse bg-surface text-left text-sm">
          <caption className="bg-surface-muted px-4 py-2 text-left font-medium">Fontes de dados e coletas</caption>
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Fonte</th>
              <th scope="col" className="px-3 py-2 font-medium">Estado</th>
              <th scope="col" className="px-3 py-2 font-medium">Última coleta ok</th>
              <th scope="col" className="px-3 py-2 font-medium">Disponibilidade 7 / 30 dias</th>
              <th scope="col" className="px-3 py-2 font-medium">Duração média</th>
              <th scope="col" className="px-3 py-2 font-medium">Rejeitados</th>
              <th scope="col" className="px-3 py-2 font-medium">Cobertura</th>
              <th scope="col" className="px-3 py-2 font-medium">Última falha</th>
            </tr>
          </thead>
          <tbody>
            {health.data.map((s) => (
              <tr key={s.code} className="border-t border-surface-border align-top">
                <th scope="row" className="px-3 py-2 font-medium">{s.name}</th>
                <td className="px-3 py-2">
                  <StatusBadge
                    tone={TONES[s.freshness] ?? "unknown"}
                    label={(FRESHNESS_LABELS as Record<string, string>)[s.freshness] ?? s.freshness}
                  />
                  <span className="mt-1 block text-xs text-ink-muted">
                    {(REASON_LABELS as Record<string, string>)[s.reason] ?? s.reason}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs">
                  {s.last_success_at ? formatDateTime(s.last_success_at) : "—"}
                  <span className="block text-ink-muted">esperado a cada {num(s.expected_interval_h, 0)} h</span>
                </td>
                <td className="px-3 py-2 tabular-nums">
                  {pct(s.availability_7d)} / {pct(s.availability_30d)}
                  <span className="block text-xs text-ink-muted">
                    {s.success_7d} de {s.runs_7d} · {s.success_30d} de {s.runs_30d}
                  </span>
                </td>
                <td className="px-3 py-2 tabular-nums">{s.mean_duration_s === null ? "—" : `${num(s.mean_duration_s)} s`}</td>
                <td className="px-3 py-2 tabular-nums">{pct(s.rejected_rate, 1)}</td>
                <td className="px-3 py-2 text-xs">{s.coverage ?? "—"}</td>
                <td className="px-3 py-2 text-xs">
                  {s.last_failure_at ? (
                    <>
                      {formatDateTime(s.last_failure_at)}
                      <span className="block break-words text-ink-muted">{s.last_failure}</span>
                    </>
                  ) : (
                    "nenhuma"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ink-muted">
        Disponibilidade = coletas bem-sucedidas ÷ coletas tentadas no período. Rejeitados =
        registros recusados na validação ÷ recebidos (30 dias).
      </p>
    </div>
  );
}
