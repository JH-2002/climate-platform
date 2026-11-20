import { StatusBadge } from "@/components/ui/StatusBadge";
import { CATEGORIES, CATEGORY_ORDER } from "@/features/risk/categories";
import type { RiskCategory, RiskSummary } from "@/features/risk/types";
import { FRESHNESS_LABELS } from "@/features/sources/types";
import { formatDateTime } from "@/lib/format";
import { RiskSwatch } from "./RiskBadge";

interface RiskSummaryViewProps {
  summary: RiskSummary;
  selected: RiskCategory | null;
  onSelect: (category: RiskCategory | null) => void;
}

function freshnessLabel(value: string): string {
  return (FRESHNESS_LABELS as Record<string, string>)[value] ?? value;
}

/** Contagem por categoria (clicável como filtro) e de onde vem a estimativa. */
export function RiskSummaryView({ summary, selected, onSelect }: RiskSummaryViewProps) {
  const { run } = summary;
  if (!run) {
    return (
      <p role="status" className="rounded-lg border border-surface-border bg-surface p-4 text-sm">
        Ainda não há estimativa calculada. Ela aparece depois da primeira coleta da previsão e das
        camadas do GeoSampa.
      </p>
    );
  }
  return (
    <section aria-labelledby="resumo-titulo" className="space-y-3">
      <h2 id="resumo-titulo" className="sr-only">
        Resumo por categoria
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {CATEGORY_ORDER.map((category) => {
          const info = CATEGORIES[category];
          const active = selected === category;
          return (
            <li key={category}>
              <button
                type="button"
                aria-pressed={active}
                onClick={() => onSelect(active ? null : category)}
                className={`flex w-full flex-col items-start gap-1 rounded-lg border bg-surface p-3 text-left hover:bg-surface-muted ${active ? "ring-2 ring-accent" : ""}`}
                style={{ borderColor: info.color }}
              >
                <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: info.text }}>
                  <RiskSwatch category={category} />
                  {info.label}
                </span>
                <span className="text-2xl font-semibold tabular-nums">{summary.counts[category] ?? 0}</span>
                <span className="text-xs text-ink-muted">setores</span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="space-y-1 text-xs text-ink-muted">
        <p>
          Calculado em{" "}
          <time dateTime={run.computed_at}>{formatDateTime(run.computed_at)}</time>, válido por 24 h ·
          previsão coletada em{" "}
          {run.forecast_issued_at ? (
            <time dateTime={run.forecast_issued_at}>{formatDateTime(run.forecast_issued_at)}</time>
          ) : (
            "—"
          )}{" "}
          · motor <code>{run.engine_version}</code> · {summary.attribution}
        </p>
        {(run.stale || run.forecast_freshness !== "FRESH") && (
          <p className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="warn" label={run.stale ? "Estimativa desatualizada" : freshnessLabel(run.forecast_freshness)} />
            {run.stale
              ? "A última estimativa tem mais de 3 horas; confira o estado do sistema."
              : "A previsão usada não está em dia; setores podem aparecer como desconhecidos."}
          </p>
        )}
      </div>
    </section>
  );
}
