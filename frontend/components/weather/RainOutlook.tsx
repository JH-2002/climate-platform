import type { PrecipitationOutlook } from "@/features/weather/types";
import { formatNumber } from "@/lib/format";

interface RainOutlookProps {
  outlook: PrecipitationOutlook[];
  observationsAvailable: boolean;
}

function label(hours: number): string {
  return hours === 1 ? "Próxima 1 h" : `Próximas ${hours} h`;
}

/** Chuva prevista acumulada (FR-043, BR-041) e o estado da chuva medida (BR-043). */
export function RainOutlook({ outlook, observationsAvailable }: RainOutlookProps) {
  return (
    <section
      aria-labelledby="chuva-titulo"
      className="space-y-3 rounded-lg border border-surface-border bg-surface p-5"
    >
      <h2 id="chuva-titulo" className="text-lg font-semibold">
        Chuva
      </h2>
      <div>
        <h3 className="text-sm font-medium">Prevista (modelo)</h3>
        <ul className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {outlook.map((item) => (
            <li key={item.hours} className="rounded-md bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">{label(item.hours)}</p>
              <p className="text-lg font-semibold tabular-nums">
                {formatNumber(item.total_mm)} <span className="text-sm font-normal">mm</span>
              </p>
              {!item.complete && (
                <p className="text-xs text-status-warn">
                  Parcial: {item.hours_available} de {item.hours} h disponíveis
                </p>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="text-sm font-medium">Medida (estações)</h3>
        <p className="text-sm text-ink-muted">
          {observationsAvailable
            ? "Disponível nas estações próximas."
            : "Indisponível: as medições das estações do INMET aguardam o token de acesso."}
        </p>
      </div>
    </section>
  );
}
