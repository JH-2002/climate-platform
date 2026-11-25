import { StatusBadge, type BadgeTone } from "@/components/ui/StatusBadge";
import {
  FRESHNESS_LABELS,
  REASON_LABELS,
  type Freshness,
  type SourceStatus,
} from "@/features/sources/types";
import { formatDateTime } from "@/lib/format";

const TONE: Record<Freshness, BadgeTone> = {
  FRESH: "ok",
  DELAYED: "warn",
  STALE: "warn",
  UNAVAILABLE: "error",
  UNKNOWN: "unknown",
};

interface SourcesViewProps {
  state: "loading" | "success" | "error";
  items?: SourceStatus[];
  errorMessage?: string;
  onRetry: () => void;
}

function formatInterval(seconds: number): string {
  if (seconds % 86400 === 0) return `a cada ${seconds / 86400} dia(s)`;
  if (seconds % 3600 === 0) return `a cada ${seconds / 3600} h`;
  return `a cada ${Math.round(seconds / 60)} min`;
}

export function SourcesView({ state, items, errorMessage, onRetry }: SourcesViewProps) {
  return (
    <section aria-labelledby="fontes-titulo" className="space-y-3">
      <h2 id="fontes-titulo" className="text-lg font-semibold">
        Saúde das fontes de dados
      </h2>

      {state === "loading" && (
        <div role="status" aria-live="polite" className="h-24 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
          <span className="sr-only">Carregando o estado das fontes…</span>
        </div>
      )}

      {state === "error" && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface p-4">
          <p className="text-sm text-ink-muted">
            Não foi possível obter o estado das fontes. {errorMessage}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {state === "success" && items && items.length === 0 && (
        <p className="text-sm text-ink-muted">Nenhuma fonte cadastrada.</p>
      )}

      {state === "success" && items && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((source) => (
            <li
              key={source.code}
              className="space-y-2 rounded-lg border border-surface-border bg-surface p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-medium">{source.name}</h3>
                <StatusBadge tone={TONE[source.freshness]} label={FRESHNESS_LABELS[source.freshness]} />
              </div>
              <p className="text-sm text-ink-muted">{REASON_LABELS[source.reason]}.</p>
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                <div>
                  <dt className="inline text-ink-muted">Última coleta bem-sucedida: </dt>
                  <dd className="inline">
                    {source.last_success_at ? (
                      <time dateTime={source.last_success_at} title={`${source.last_success_at} (UTC)`}>
                        {formatDateTime(source.last_success_at)}
                      </time>
                    ) : (
                      "nunca"
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="inline text-ink-muted">Frequência esperada: </dt>
                  <dd className="inline">{formatInterval(source.expected_interval_s)}</dd>
                </div>
                <div>
                  <dt className="inline text-ink-muted">Acesso: </dt>
                  <dd className="inline">{source.access_method}</dd>
                </div>
                <div>
                  <dt className="inline text-ink-muted">Licença: </dt>
                  <dd className="inline">{source.license}</dd>
                </div>
              </dl>
              <p className="text-xs text-ink-muted">{source.attribution}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
