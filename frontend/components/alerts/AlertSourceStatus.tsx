import { StatusBadge, type BadgeTone } from "@/components/ui/StatusBadge";
import type { AlertSource, Freshness } from "@/features/alerts/types";
import { FRESHNESS_LABELS } from "@/features/sources/types";
import { formatDateTime } from "@/lib/format";

const TONE: Record<Freshness, BadgeTone> = {
  FRESH: "ok",
  DELAYED: "warn",
  STALE: "warn",
  UNAVAILABLE: "error",
  UNKNOWN: "unknown",
};

/** Frescor das fontes de alerta: "nenhum alerta" só vale com elas em dia (BR-144). */
export function AlertSourceStatus({ sources, ok }: { sources: AlertSource[]; ok: boolean }) {
  return (
    <section aria-labelledby="fontes-alerta" className="space-y-2 rounded-lg border border-surface-border bg-surface p-4">
      <h2 id="fontes-alerta" className="text-sm font-semibold">
        Fontes dos alertas oficiais
      </h2>
      <ul className="space-y-1 text-sm">
        {sources.map((s) => (
          <li key={s.code} className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={TONE[s.freshness]} label={FRESHNESS_LABELS[s.freshness]} />
            <span>{s.name}</span>
            <span className="text-ink-muted">
              {s.last_success_at ? `· última coleta ${formatDateTime(s.last_success_at)}` : "· ainda sem coleta"}
            </span>
          </li>
        ))}
      </ul>
      {!ok && (
        <p role="status" className="text-sm font-medium text-status-warn">
          Uma fonte de alertas está atrasada ou indisponível: a ausência de alertas aqui não quer dizer
          que não haja alerta. Consulte também os canais oficiais.
        </p>
      )}
    </section>
  );
}
