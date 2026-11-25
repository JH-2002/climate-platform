import type { DailyValues } from "@/features/weather/types";
import { formatDay, formatNumber } from "@/lib/format";

export function DailyTable({ days }: { days: DailyValues[] }) {
  return (
    <section aria-labelledby="dias-titulo" className="space-y-3">
      <h2 id="dias-titulo" className="text-lg font-semibold">
        Próximos dias
      </h2>
      {days.length === 0 ? (
        <p className="text-sm text-ink-muted">Sem previsão diária coletada para este local.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-surface-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Previsão por dia">
          <table className="w-full border-collapse bg-surface text-left text-sm">
            <caption className="sr-only">Previsão diária: temperaturas, chuva e probabilidade</caption>
            <thead className="bg-surface-muted text-ink-muted">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Dia</th>
                <th scope="col" className="px-4 py-2 font-medium">Máx. (°C)</th>
                <th scope="col" className="px-4 py-2 font-medium">Mín. (°C)</th>
                <th scope="col" className="px-4 py-2 font-medium">Chuva (mm)</th>
                <th scope="col" className="px-4 py-2 font-medium">Prob. de chuva (%)</th>
              </tr>
            </thead>
            <tbody>
              {days.map((day) => (
                <tr key={day.date} className="border-t border-surface-border tabular-nums">
                  <th scope="row" className="px-4 py-2 font-medium capitalize">{formatDay(day.date)}</th>
                  <td className="px-4 py-2">{formatNumber(day.air_temperature_max)}</td>
                  <td className="px-4 py-2">{formatNumber(day.air_temperature_min)}</td>
                  <td className="px-4 py-2">{formatNumber(day.precipitation_sum)}</td>
                  <td className="px-4 py-2">{formatNumber(day.precipitation_probability_max, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
