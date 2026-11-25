import { STATUS_LABELS, areaText, severityIcon, validityText } from "@/features/alerts/labels";
import type { OfficialAlert, OfficialStatus } from "@/features/alerts/types";
import { formatDateTime } from "@/lib/format";

// Situação com ícone e texto próprios (o ✕ do selo genérico leria como "cancelado").
const STATUS_STYLE: Record<OfficialStatus, { icon: string; className: string }> = {
  ACTIVE: { icon: "●", className: "border-status-error/50 text-status-error" },
  UPCOMING: { icon: "◷", className: "border-status-warn/50 text-status-warn" },
  EXPIRED: { icon: "–", className: "border-surface-border text-ink-muted" },
  CANCELLED: { icon: "–", className: "border-surface-border text-ink-muted" },
  SUPERSEDED: { icon: "–", className: "border-surface-border text-ink-muted" },
};

const SEVERITY_STYLE: Record<string, string> = {
  Extreme: "border-status-error bg-status-error/10 text-status-error",
  Severe: "border-status-error/60 bg-status-error/5 text-status-error",
  Moderate: "border-status-warn/60 bg-status-warn/5 text-status-warn",
};

/** Alerta oficial com o texto da fonte, sem resumo nem reescrita (BR-141). */
export function OfficialAlertCard({ alert, highlighted = false }: { alert: OfficialAlert; highlighted?: boolean }) {
  const titleId = `alerta-${alert.id}-titulo`;
  const severityText = alert.level_name ?? `Severidade ${alert.severity_label.toLowerCase()}`;
  const showDescription = alert.description && alert.description !== alert.headline;
  return (
    <article
      id={`alerta-${alert.id}`}
      aria-labelledby={titleId}
      className={`space-y-3 rounded-lg border bg-surface p-4 ${
        highlighted ? "border-accent ring-2 ring-accent" : "border-surface-border"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded bg-ink px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
          {alert.category_label}
        </span>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-medium ${STATUS_STYLE[alert.status].className}`}>
          <span aria-hidden="true">{STATUS_STYLE[alert.status].icon}</span>
          {STATUS_LABELS[alert.status]}
        </span>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-medium ${
            SEVERITY_STYLE[alert.severity ?? ""] ?? "border-surface-border text-ink-muted"
          }`}
        >
          {alert.color && (
            <span aria-hidden="true" className="h-3 w-3 rounded-full border border-ink/20" style={{ backgroundColor: alert.color }} />
          )}
          <span aria-hidden="true">{severityIcon(alert.severity)}</span>
          {severityText}
        </span>
      </div>
      <h3 id={titleId} className="text-base font-semibold">
        {alert.headline ?? alert.event ?? "Alerta oficial"}
      </h3>
      <dl className="grid gap-1 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-3">
        <dt className="font-medium text-ink-muted">Vigência</dt>
        <dd>{validityText(alert)}</dd>
        <dt className="font-medium text-ink-muted">Área</dt>
        <dd>{areaText(alert)}</dd>
        {alert.event && (
          <>
            <dt className="font-medium text-ink-muted">Evento</dt>
            <dd>{alert.event}</dd>
          </>
        )}
      </dl>
      {showDescription && <p className="text-sm">{alert.description}</p>}
      {alert.instruction && (
        <div className="rounded-md bg-surface-muted p-3 text-sm">
          <p className="font-medium">O que fazer (orientação da fonte)</p>
          <p>{alert.instruction}</p>
        </div>
      )}
      <p className="text-xs text-ink-muted">
        Fonte: {alert.sender_name ?? alert.attribution} · enviado em {formatDateTime(alert.sent_at)} ·{" "}
        {alert.attribution}
        {alert.web && (
          <>
            {" · "}
            <a href={alert.web} target="_blank" rel="noopener noreferrer" className="font-medium text-accent underline">
              Página da fonte
            </a>
          </>
        )}
      </p>
    </article>
  );
}
