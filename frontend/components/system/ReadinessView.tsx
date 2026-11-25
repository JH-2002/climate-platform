import { StatusBadge, type BadgeTone } from "@/components/ui/StatusBadge";
import {
  COMPONENT_LABELS,
  type ComponentStatus,
  type ReadinessReport,
  type ReadinessViewState,
} from "@/features/system/types";
import { formatDateTime, formatLatency } from "@/lib/format";

interface ReadinessViewProps {
  state: ReadinessViewState;
  report?: ReadinessReport;
  errorMessage?: string;
  correlationId?: string | null;
  isRefreshing?: boolean;
  onRetry: () => void;
}

const COMPONENT_TONE: Record<ComponentStatus, { tone: BadgeTone; label: string }> = {
  ok: { tone: "ok", label: "Operacional" },
  unavailable: { tone: "error", label: "Indisponível" },
};

const SUMMARY: Record<Exclude<ReadinessViewState, "loading">, { tone: BadgeTone; label: string; text: string }> = {
  success: { tone: "ok", label: "Todos os componentes operacionais", text: "" },
  degraded: {
    tone: "warn",
    label: "Operação degradada",
    text: "Um ou mais componentes não responderam. Veja os detalhes abaixo.",
  },
  error: {
    tone: "error",
    label: "API inacessível",
    text: "Não foi possível obter o estado do sistema.",
  },
  offline: {
    tone: "unknown",
    label: "Sem conexão",
    text: "Seu navegador está sem internet. O estado será atualizado quando a conexão voltar.",
  },
};

function RetryButton({ onRetry, busy }: { onRetry: () => void; busy: boolean }) {
  return (
    <button
      type="button"
      onClick={onRetry}
      disabled={busy}
      className="rounded-md border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
    >
      {busy ? "Verificando…" : "Tentar novamente"}
    </button>
  );
}

export function ReadinessView({
  state,
  report,
  errorMessage,
  correlationId,
  isRefreshing = false,
  onRetry,
}: ReadinessViewProps) {
  if (state === "loading") {
    return (
      <div role="status" aria-live="polite" className="space-y-3">
        <span className="sr-only">Verificando o estado do sistema…</span>
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} aria-hidden="true" className="h-12 animate-pulse rounded-md bg-surface-muted motion-reduce:animate-none" />
        ))}
      </div>
    );
  }

  const summary = SUMMARY[state];

  return (
    <section aria-labelledby="readiness-summary" className="space-y-4">
      <div
        role={state === "success" ? "status" : "alert"}
        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface p-4"
      >
        <div className="space-y-1">
          <h2 id="readiness-summary" className="text-base font-semibold">
            <StatusBadge tone={summary.tone} label={summary.label} />
          </h2>
          {summary.text && <p className="text-sm text-ink-muted">{summary.text}</p>}
          {state === "error" && errorMessage && (
            <p className="text-sm text-ink-muted">Detalhe: {errorMessage}</p>
          )}
          {correlationId && state === "error" && (
            <p className="text-xs text-ink-muted">
              Código para suporte: <code>{correlationId}</code>
            </p>
          )}
        </div>
        {state !== "success" && <RetryButton onRetry={onRetry} busy={isRefreshing} />}
      </div>

      {report && (
        <>
          <div className="overflow-x-auto rounded-lg border border-surface-border">
          <table className="w-full border-collapse bg-surface text-left text-sm">
            <caption className="sr-only">Estado de cada componente do sistema</caption>
            <thead className="bg-surface-muted text-ink-muted">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Componente</th>
                <th scope="col" className="px-4 py-2 font-medium">Estado</th>
                <th scope="col" className="px-4 py-2 font-medium">Latência</th>
                <th scope="col" className="px-4 py-2 font-medium">Detalhes</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.components).map(([name, component]) => {
                const tone = COMPONENT_TONE[component.status];
                const info = Object.entries(component.info)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(", ");
                return (
                  <tr key={name} className="border-t border-surface-border">
                    <th scope="row" className="px-4 py-3 font-medium">
                      {COMPONENT_LABELS[name] ?? name}
                    </th>
                    <td className="px-4 py-3">
                      <StatusBadge tone={tone.tone} label={tone.label} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{formatLatency(component.latency_ms)}</td>
                    <td className="break-all px-4 py-3 text-ink-muted">
                      {component.detail ?? (info || "—")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
          <p className="text-xs text-ink-muted">
            Verificado em{" "}
            <time dateTime={report.checked_at} title={`${report.checked_at} (UTC)`}>
              {formatDateTime(report.checked_at)}
            </time>{" "}
            (horário de Brasília). Atualização automática a cada 30 s
            {isRefreshing ? " — atualizando…" : "."}
          </p>
        </>
      )}
    </section>
  );
}
