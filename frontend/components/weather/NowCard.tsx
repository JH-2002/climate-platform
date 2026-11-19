import type { HourlyValues } from "@/features/weather/types";
import { formatHour, formatNumber } from "@/lib/format";

interface NowCardProps {
  now: HourlyValues | null;
}

function Metric({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">
        {formatNumber(value)} <span className="text-sm font-normal text-ink-muted">{unit}</span>
      </dd>
    </div>
  );
}

/** "Agora" = previsão da hora corrente, rotulada como estimativa (ADR-007, AC-044). */
export function NowCard({ now }: NowCardProps) {
  return (
    <section
      aria-labelledby="agora-titulo"
      className="space-y-3 rounded-lg border border-surface-border bg-surface p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="agora-titulo" className="text-lg font-semibold">
          Agora {now && <span className="text-sm font-normal text-ink-muted">({formatHour(now.valid_at)})</span>}
        </h2>
        <span className="rounded-full border border-status-warn/40 bg-status-warn/10 px-2.5 py-0.5 text-xs font-medium text-status-warn">
          Estimativa de modelo — não é medição
        </span>
      </div>
      {now ? (
        <>
          <p className="text-4xl font-semibold tabular-nums">
            {formatNumber(now.air_temperature)} <span className="text-2xl text-ink-muted">°C</span>
          </p>
          <dl className="grid grid-cols-3 gap-4">
            <Metric label="Chuva na hora" value={now.precipitation} unit="mm" />
            <Metric label="Umidade" value={now.relative_humidity} unit="%" />
            <Metric label="Vento" value={now.wind_speed === null ? null : now.wind_speed * 3.6} unit="km/h" />
          </dl>
        </>
      ) : (
        <p className="text-sm text-ink-muted">
          A previsão coletada não cobre a hora atual. Verifique a coleta em Estado do sistema.
        </p>
      )}
    </section>
  );
}
