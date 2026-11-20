import type { ReactNode } from "react";
import { kindLabel } from "@/features/analytics/kinds";

export interface TableColumn {
  key: string;
  label: string;
  format?: (value: unknown) => string;
}

interface ChartFrameProps {
  id: string;
  title: string;
  /** Resumo em texto do que o gráfico mostra (alternativa ao visual, NFR-083). */
  summary: string;
  kind: string;
  source: string | null;
  notes?: string[];
  rows: Record<string, unknown>[];
  columns: TableColumn[];
  children: ReactNode;
}

/** Moldura comum: título, resumo, gráfico, fonte e tipo, e a mesma informação em tabela. */
export function ChartFrame({ id, title, summary, kind, source, notes = [], rows, columns, children }: ChartFrameProps) {
  return (
    <section aria-labelledby={id} className="space-y-2 rounded-lg border border-surface-border bg-surface p-4">
      <h3 id={id} className="font-semibold">
        {title}
      </h3>
      <p className="text-sm text-ink-muted">{summary}</p>
      <div className="h-72" role="img" aria-label={`${title}. ${summary} Os dados estão na tabela abaixo do gráfico.`}>
        {children}
      </div>
      <p className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
        <span className="rounded border border-surface-border px-1.5 py-0.5 font-medium text-ink">{kindLabel(kind)}</span>
        {source && <span>{source}</span>}
      </p>
      {notes.map((note) => (
        <p key={note} className="text-xs text-ink-muted">
          {note}
        </p>
      ))}
      <details className="text-sm">
        <summary className="cursor-pointer text-accent">Ver os dados em tabela</summary>
        <div className="mt-2 max-h-80 overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <caption className="sr-only">{title}</caption>
            <thead className="sticky top-0 bg-surface text-ink-muted">
              <tr>
                {columns.map((c) => (
                  <th key={c.key} scope="col" className="py-1 pr-3 font-medium">
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-t border-surface-border">
                  {columns.map((c) => (
                    <td key={c.key} className="py-1 pr-3 tabular-nums">
                      {c.format ? c.format(row[c.key]) : String(row[c.key] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
