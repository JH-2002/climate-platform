"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HourlyValues } from "@/features/weather/types";
import { formatHour, formatNumber } from "@/lib/format";

interface HourlyChartProps {
  hours: HourlyValues[];
}

/** Temperatura (linha) e chuva (barras) nas próximas 48 h, com tabela equivalente (NFR-041). */
export function HourlyChart({ hours }: HourlyChartProps) {
  const data = hours.map((h) => ({ ...h, hora: formatHour(h.valid_at) }));
  return (
    <section aria-labelledby="horas-titulo" className="space-y-3">
      <h2 id="horas-titulo" className="text-lg font-semibold">
        Próximas 48 horas
      </h2>
      {hours.length === 0 ? (
        <p className="text-sm text-ink-muted">Sem previsão horária coletada para este local.</p>
      ) : (
        <>
          <div
            className="h-64 rounded-lg border border-surface-border bg-surface p-2"
            role="img"
            aria-label="Gráfico de temperatura (linha, °C) e chuva (barras, mm) por hora. Os mesmos dados estão na tabela abaixo."
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
                <XAxis dataKey="hora" interval={5} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="temp" unit=" °C" tick={{ fontSize: 12 }} width={56} />
                <YAxis yAxisId="chuva" orientation="right" unit=" mm" tick={{ fontSize: 12 }} width={56} />
                <Tooltip
                  formatter={(value, name) =>
                    String(name) === "Chuva"
                      ? `${formatNumber(Number(value))} mm`
                      : `${formatNumber(Number(value))} °C`
                  }
                />
                <Bar yAxisId="chuva" dataKey="precipitation" name="Chuva" fill="#7fb3c9" />
                <Line
                  yAxisId="temp"
                  type="monotone"
                  dataKey="air_temperature"
                  name="Temperatura"
                  stroke="#b42318"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <details className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
            <summary className="cursor-pointer font-medium">Ver dados em tabela</summary>
            <div className="mt-2 max-h-72 overflow-auto">
              <table className="w-full border-collapse text-left tabular-nums">
                <caption className="sr-only">Previsão horária</caption>
                <thead className="text-ink-muted">
                  <tr>
                    <th scope="col" className="py-1 pr-4 font-medium">Hora</th>
                    <th scope="col" className="py-1 pr-4 font-medium">Temp. (°C)</th>
                    <th scope="col" className="py-1 pr-4 font-medium">Chuva (mm)</th>
                    <th scope="col" className="py-1 pr-4 font-medium">Umidade (%)</th>
                    <th scope="col" className="py-1 pr-4 font-medium">Vento (km/h)</th>
                  </tr>
                </thead>
                <tbody>
                  {hours.map((h) => (
                    <tr key={h.valid_at} className="border-t border-surface-border">
                      <th scope="row" className="py-1 pr-4 font-normal">{formatHour(h.valid_at)}</th>
                      <td className="py-1 pr-4">{formatNumber(h.air_temperature)}</td>
                      <td className="py-1 pr-4">{formatNumber(h.precipitation)}</td>
                      <td className="py-1 pr-4">{formatNumber(h.relative_humidity, 0)}</td>
                      <td className="py-1 pr-4">
                        {formatNumber(h.wind_speed === null ? null : h.wind_speed * 3.6)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
