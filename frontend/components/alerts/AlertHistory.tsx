"use client";

import Link from "next/link";
import { useState } from "react";
import { useAlertHistory } from "@/features/alerts/hooks";
import { CATEGORY_TITLES, STATUS_LABELS, alertHref } from "@/features/alerts/labels";
import type { AlertCategory, AlertHistory as History, OfficialStatus } from "@/features/alerts/types";
import { formatDateTime } from "@/lib/format";

const CATEGORIES = Object.keys(CATEGORY_TITLES) as AlertCategory[];

function statusText(status: string): string {
  if (status === "OPEN") return "Aberto";
  if (status === "CLOSED") return "Encerrado";
  return STATUS_LABELS[status as OfficialStatus] ?? status;
}

export function AlertHistoryTable({ history }: { history: History }) {
  if (history.items.length === 0) return <p className="text-sm">Nenhum alerta neste período.</p>;
  return (
    <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Histórico de alertas">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Alertas dos últimos 7 dias</caption>
        <thead className="text-ink-muted">
          <tr>
            <th scope="col" className="py-1 pr-3 font-medium">Início</th>
            <th scope="col" className="py-1 pr-3 font-medium">Fim</th>
            <th scope="col" className="py-1 pr-3 font-medium">Categoria</th>
            <th scope="col" className="py-1 pr-3 font-medium">Alerta</th>
            <th scope="col" className="py-1 pr-3 font-medium">Nível</th>
            <th scope="col" className="py-1 font-medium">Situação</th>
          </tr>
        </thead>
        <tbody>
          {history.items.map((e) => (
            <tr key={`${e.kind}-${e.id}`} className="border-t border-surface-border align-top">
              <td className="py-1 pr-3 whitespace-nowrap">{e.start_at ? formatDateTime(e.start_at) : "—"}</td>
              <td className="py-1 pr-3 whitespace-nowrap">{e.end_at ? formatDateTime(e.end_at) : "em aberto"}</td>
              <td className="py-1 pr-3">{e.category_label}</td>
              <td className="py-1 pr-3">
                {e.kind === "official" ? (
                  <Link href={alertHref(e.id)} className="text-accent underline">
                    {e.title}
                  </Link>
                ) : (
                  e.title
                )}
              </td>
              <td className="py-1 pr-3">{e.level_label}</td>
              <td className="py-1">{statusText(e.status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Histórico de 7 dias, com filtro por categoria (FR-146). */
export function AlertHistory() {
  const [category, setCategory] = useState<AlertCategory | null>(null);
  const [page, setPage] = useState(1);
  const query = useAlertHistory(category, page);
  const pages = query.data ? Math.max(1, Math.ceil(query.data.total / query.data.page_size)) : 1;
  return (
    <section aria-labelledby="historico" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="historico" className="text-lg font-semibold">
          Últimos 7 dias
        </h2>
        <label className="flex items-center gap-2 text-sm">
          Categoria
          <select
            value={category ?? ""}
            onChange={(e) => {
              setCategory((e.target.value || null) as AlertCategory | null);
              setPage(1);
            }}
            className="rounded-md border border-surface-border bg-surface px-2 py-1"
          >
            <option value="">Todas</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_TITLES[c]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {query.isPending && <p className="text-sm text-ink-muted">Carregando o histórico…</p>}
      {query.isError && (
        <p role="alert" className="text-sm">
          Não foi possível carregar o histórico.
        </p>
      )}
      {query.data && <AlertHistoryTable history={query.data} />}
      {pages > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded border border-surface-border px-2 py-1 disabled:opacity-50">
            Anterior
          </button>
          <span>
            Página {page} de {pages}
          </span>
          <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} className="rounded border border-surface-border px-2 py-1 disabled:opacity-50">
            Próxima
          </button>
        </div>
      )}
    </section>
  );
}
