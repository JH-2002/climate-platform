import { kindLabel } from "@/features/analytics/kinds";
import type { Insight } from "@/features/analytics/types";
import { formatNumber } from "@/lib/format";

function metricValue(value: number | string | null, unit: string): string {
  if (value === null) return "—";
  if (typeof value === "string") return value;
  return `${formatNumber(value, Number.isInteger(value) ? 0 : 1)}${unit ? ` ${unit}` : ""}`;
}

/** Insights por regra (FR-085): frase + métricas verificáveis, sem causas inventadas. */
export function InsightList({ items, notes, rulesVersion }: { items: Insight[]; notes: string[]; rulesVersion: string }) {
  return (
    <div className="space-y-3">
      {items.length === 0 ? (
        <p className="rounded-lg border border-surface-border bg-surface p-4 text-sm text-ink-muted">
          Nenhuma regra disparou agora: chuva prevista, acumulados, risco estimado e fontes estão
          dentro dos limites definidos.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((insight, index) => (
            <li
              key={`${insight.code}-${index}`}
              className={`rounded-lg border bg-surface p-4 text-sm ${insight.severity === "atencao" ? "border-l-4 border-status-warn" : "border-surface-border"}`}
            >
              <p className="flex gap-2">
                <span
                  aria-hidden="true"
                  className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${insight.severity === "atencao" ? "bg-status-warn text-white" : "border border-surface-border"}`}
                >
                  {insight.severity === "atencao" ? "!" : "i"}
                </span>
                <span>
                  <span className="sr-only">{insight.severity === "atencao" ? "Atenção: " : "Informação: "}</span>
                  {insight.text}
                </span>
              </p>
              <details className="mt-2 pl-7 text-xs text-ink-muted">
                <summary className="cursor-pointer">Números usados ({insight.code})</summary>
                <table className="mt-1 w-full border-collapse text-left">
                  <thead>
                    <tr>
                      <th scope="col" className="py-0.5 pr-3 font-medium">Métrica</th>
                      <th scope="col" className="py-0.5 pr-3 font-medium">Valor</th>
                      <th scope="col" className="py-0.5 pr-3 font-medium">Tipo</th>
                      <th scope="col" className="py-0.5 font-medium">Fonte</th>
                    </tr>
                  </thead>
                  <tbody>
                    {insight.metrics.map((m) => (
                      <tr key={m.name}>
                        <th scope="row" className="py-0.5 pr-3 font-normal">{m.name}</th>
                        <td className="py-0.5 pr-3 tabular-nums">{metricValue(m.value, m.unit)}</td>
                        <td className="py-0.5 pr-3">{kindLabel(m.kind)}</td>
                        <td className="py-0.5">{m.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </li>
          ))}
        </ul>
      )}
      {notes.map((note) => (
        <p key={note} className="text-xs text-ink-muted">{note}</p>
      ))}
      <p className="text-xs text-ink-muted">
        Regras documentadas na spec 006 (versão <code>{rulesVersion}</code>). Os textos só repetem os
        números ao lado; não indicam causas.
      </p>
    </div>
  );
}
