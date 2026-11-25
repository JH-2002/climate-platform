import { StatusBadge, type BadgeTone } from "@/components/ui/StatusBadge";
import { STATUS_LABELS, formatBytes } from "@/features/reports/form";
import type { ReportRequest, ReportStatus } from "@/features/reports/types";
import { formatDateTime } from "@/lib/format";

const TONE: Record<ReportStatus, BadgeTone> = {
  QUEUED: "unknown",
  RUNNING: "warn",
  DONE: "ok",
  FAILED: "error",
  EXPIRED: "unknown",
};

/** Pedidos deste navegador, com andamento e download (FR-156, AC-156). */
export function ReportList({ items }: { items: ReportRequest[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-ink-muted">Nenhum relatório pedido neste navegador ainda.</p>;
  }
  return (
    <ul className="divide-y divide-surface-border rounded-lg border border-surface-border bg-surface">
      {items.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 p-3 text-sm">
          <span className="min-w-0 flex-1 basis-64">
            <span className="block font-medium">
              {r.title} <span className="font-normal uppercase text-ink-muted">· {r.format}</span>
              {r.mode === "SIMULATION" && <span className="ml-2 rounded bg-violet-700 px-1.5 py-0.5 text-xs font-semibold text-white">SIMULAÇÃO</span>}
            </span>
            <span className="block text-xs text-ink-muted">
              Pedido em {formatDateTime(r.created_at)}
              {r.expires_at && r.status === "DONE" && ` · disponível até ${formatDateTime(r.expires_at)}`}
            </span>
            {r.error && <span className="block text-xs text-status-error">{r.error}</span>}
          </span>
          <span aria-live="polite">
            <StatusBadge tone={TONE[r.status]} label={STATUS_LABELS[r.status]} />
          </span>
          {r.download_url ? (
            <a href={r.download_url} download={r.filename ?? undefined} className="rounded-md border border-accent px-3 py-1.5 font-medium text-accent hover:bg-accent hover:text-white">
              Baixar {r.filename ?? ""} ({formatBytes(r.bytes)})
            </a>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
