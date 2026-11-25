import { StatusBadge } from "@/components/ui/StatusBadge";
import { FRESHNESS_LABELS, REASON_LABELS } from "@/features/sources/types";
import type { ForecastResponse } from "@/features/weather/types";
import { formatDateTime, formatNumber } from "@/lib/format";

/** Origem do dado: modelo, fonte, coleta e frescor (FR-047). */
export function SourceNote({ forecast }: { forecast: ForecastResponse }) {
  const { source, point } = forecast;
  return (
    <div className="space-y-1 text-xs text-ink-muted">
      <p>
        Previsão de modelo (não é medição) para o ponto de grade a{" "}
        {formatNumber(point.distance_km, 1)} km do local. Coleta:{" "}
        <time dateTime={forecast.issued_at} title={`${forecast.issued_at} (UTC)`}>
          {formatDateTime(forecast.issued_at)}
        </time>
        . {source.attribution}.
      </p>
      {source.freshness !== "FRESH" && (
        <p className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="warn" label={FRESHNESS_LABELS[source.freshness]} />
          {REASON_LABELS[source.reason]}.
        </p>
      )}
    </div>
  );
}
