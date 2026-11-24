"use client";

import { Area, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/analytics/ChartFrame";
import type { Profile } from "@/features/geo/types";
import { formatNumber } from "@/lib/format";

const km = (m: number) => `${formatNumber(m / 1000, 1)} km`;

/** Perfil de elevação (FR-124) com os córregos e setores cruzados; mesma informação em tabela. */
export function ProfileChart({ profile }: { profile: Profile }) {
  const drainage = profile.crossings.filter((c) => c.kind === "drainage");
  const sectors = profile.crossings.filter((c) => c.kind === "sector");
  const lowest = profile.samples.reduce<(typeof profile.samples)[number] | null>(
    (min, s) => (s.elevation_m !== null && (min === null || s.elevation_m < (min.elevation_m ?? Infinity)) ? s : min),
    null,
  );
  const summary =
    `${km(profile.length_m)} de extensão; elevação de ${formatNumber(profile.elevation_min_m, 0)} a ` +
    `${formatNumber(profile.elevation_max_m, 0)} m (sobe ${formatNumber(profile.gain_m, 0)} m e desce ` +
    `${formatNumber(profile.loss_m, 0)} m no total)` +
    (lowest ? `; ponto mais baixo a ${km(lowest.distance_m)} do início.` : ".") +
    (drainage.length > 0 ? ` Cruza ${drainage.length} curso(s) d’água` : " Não cruza curso d’água mapeado") +
    (sectors.length > 0 ? ` e ${sectors.length} setor(es) de risco.` : ".");
  const rows = profile.samples.map((s) => ({
    distancia: s.distance_m,
    elevacao: s.elevation_m,
  }));
  return (
    <div className="space-y-3">
      <ChartFrame
        id="perfil-titulo"
        title="Perfil de elevação"
        summary={summary}
        kind="DERIVED"
        source={`Copernicus DEM GLO-30, amostra a cada ${profile.step_m} m; drenagem e setores: GeoSampa`}
        notes={[profile.disclaimer]}
        rows={rows}
        columns={[
          { key: "distancia", label: "Distância (m)", format: (v) => formatNumber(v as number, 0) },
          { key: "elevacao", label: "Elevação (m)", format: (v) => (v === null ? "—" : formatNumber(v as number, 1)) },
        ]}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={profile.samples} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#d6dde3" />
            <XAxis
              dataKey="distance_m"
              type="number"
              domain={[0, profile.length_m]}
              tickFormatter={(v: number) => km(v)}
              fontSize={12}
            />
            <YAxis
              dataKey="elevation_m"
              domain={["dataMin - 5", "dataMax + 5"]}
              tickFormatter={(v: number) => `${formatNumber(v, 0)} m`}
              width={64}
              fontSize={12}
            />
            <Tooltip
              formatter={(v) => [`${formatNumber(v as number, 1)} m`, "Elevação"]}
              labelFormatter={(v) => km(v as number)}
            />
            <Area dataKey="elevation_m" type="linear" stroke="#0b5c7a" fill="#0b5c7a" fillOpacity={0.15} isAnimationActive={false} />
            {drainage.map((c) => (
              <ReferenceLine
                key={`d-${c.id}-${c.distance_m}`}
                x={c.distance_m}
                stroke="#1d6fd6"
                strokeDasharray="4 3"
                label={{ value: c.name ?? "córrego", position: "top", fontSize: 11, fill: "#1d4f91" }}
              />
            ))}
            {sectors.map((c) => (
              <ReferenceLine key={`s-${c.id}-${c.distance_m}`} x={c.distance_m} stroke="#b45309" strokeDasharray="2 2" />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>
      {profile.crossings.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-surface-border bg-surface">
          <table className="w-full border-collapse text-left text-sm">
            <caption className="px-3 py-2 text-left font-medium">O que o perfil cruza</caption>
            <thead className="text-ink-muted">
              <tr>
                <th scope="col" className="px-3 py-1 font-medium">Distância</th>
                <th scope="col" className="px-3 py-1 font-medium">O quê</th>
                <th scope="col" className="px-3 py-1 font-medium">Detalhe</th>
                <th scope="col" className="px-3 py-1 text-right font-medium">Elevação</th>
              </tr>
            </thead>
            <tbody>
              {profile.crossings.map((c) => (
                <tr key={`${c.kind}-${c.id}-${c.distance_m}`} className="border-t border-surface-border">
                  <td className="px-3 py-1 tabular-nums">{km(c.distance_m)}</td>
                  <th scope="row" className="px-3 py-1 font-normal">
                    {c.kind === "drainage" ? `Curso d’água: ${c.name ?? "sem nome"}` : `Setor de risco ${c.name}`}
                  </th>
                  <td className="px-3 py-1">{c.detail ?? "—"}</td>
                  <td className="px-3 py-1 text-right tabular-nums">
                    {c.elevation_m === null ? "—" : `${formatNumber(c.elevation_m, 0)} m`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
