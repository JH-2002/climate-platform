import { StatusBadge } from "@/components/ui/StatusBadge";
import type { NearbyStation } from "@/features/weather/api";
import { formatNumber } from "@/lib/format";

const STATUS_LABEL: Record<string, { tone: "ok" | "warn" | "error" | "unknown"; label: string }> = {
  OPERATIONAL: { tone: "ok", label: "Operante" },
  FAULT: { tone: "error", label: "Em pane" },
  INACTIVE: { tone: "unknown", label: "Desativada" },
  UNKNOWN: { tone: "unknown", label: "Situação desconhecida" },
};

interface NearbyStationsProps {
  state: "loading" | "success" | "error";
  stations?: NearbyStation[];
  observationsAvailable: boolean;
}

export function NearbyStations({ state, stations, observationsAvailable }: NearbyStationsProps) {
  return (
    <section aria-labelledby="estacoes-titulo" className="space-y-3">
      <h2 id="estacoes-titulo" className="text-lg font-semibold">
        Estações oficiais próximas
      </h2>
      {state === "loading" && <p className="text-sm text-ink-muted">Carregando estações…</p>}
      {state === "error" && (
        <p role="alert" className="text-sm text-ink-muted">
          Não foi possível carregar as estações próximas.
        </p>
      )}
      {state === "success" && stations && stations.length === 0 && (
        <p className="text-sm text-ink-muted">Nenhuma estação do INMET cadastrada a até 30 km.</p>
      )}
      {state === "success" && stations && stations.length > 0 && (
        <ul className="space-y-2">
          {stations.map((s) => {
            const status = STATUS_LABEL[s.status] ?? STATUS_LABEL.UNKNOWN!;
            return (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-surface-border bg-surface p-3"
              >
                <div>
                  <p className="font-medium">
                    {s.name} <span className="text-ink-muted">({s.code})</span>
                  </p>
                  <p className="text-xs text-ink-muted">
                    {formatNumber(s.distance_km)} km · Medições:{" "}
                    {observationsAvailable ? "disponíveis" : "indisponíveis (aguardando token do INMET)"}
                  </p>
                </div>
                <StatusBadge tone={status.tone} label={status.label} />
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
