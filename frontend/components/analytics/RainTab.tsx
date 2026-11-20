"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchClimatology, fetchDistribution, fetchSeries } from "@/features/analytics/api";
import { MONTHS_SHORT, mm, num, periodLabel } from "@/features/analytics/format";
import type { LocationInfo } from "@/features/analytics/types";
import { formatNumber } from "@/lib/format";
import { ChartFrame } from "./ChartFrame";

const REANALYSIS_NOTE =
  "Reanálise: estimativa de modelo em células de ~25 km; subestima temporais locais (no centro, ~12% abaixo da normal medida do IAG/USP). Compare um período com a média do mesmo ponto.";

function Pending({ label }: { label: string }) {
  return (
    <div role="status" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">{label}</span>
    </div>
  );
}

const axisMm = (v: number) => `${formatNumber(v, 0)}`;

interface RainTabProps {
  center: LocationInfo | null;
  yesterday: string;
}

/** Aba Chuva (FR-090): mês a mês × normal, sazonalidade, anos, distribuição e ocorrências. */
export function RainTab({ center, yesterday }: RainTabProps) {
  const year = yesterday.slice(0, 4);
  const lastFullYear = String(Number(year) - 1);
  const key = center?.key ?? "";
  const enabled = center !== null;

  const months = useQuery({
    queryKey: ["analytics", "rain-months", key, yesterday],
    queryFn: ({ signal }) =>
      fetchSeries(
        { dataset: "reanalysis-daily", variable: "precipitation_sum", location: key, start: `${year}-01-01`, end: yesterday, grain: "month", agg: "sum", compare: "normal" },
        signal,
      ),
    enabled,
  });
  const years = useQuery({
    queryKey: ["analytics", "rain-years", key, lastFullYear],
    queryFn: ({ signal }) =>
      fetchSeries(
        { dataset: "reanalysis-daily", variable: "precipitation_sum", location: key, start: "1991-01-01", end: `${lastFullYear}-12-31`, grain: "year", agg: "sum", compare: "normal" },
        signal,
      ),
    enabled,
  });
  const climReanalysis = useQuery({
    queryKey: ["analytics", "clim-reanalysis", key],
    queryFn: ({ signal }) => fetchClimatology("reanalysis-daily", "precipitation_sum", key, signal),
    enabled,
  });
  const climIag = useQuery({
    queryKey: ["analytics", "clim-iag"],
    queryFn: ({ signal }) => fetchClimatology("iag-rain-monthly", "precipitation_month", null, signal),
  });
  const distribution = useQuery({
    queryKey: ["analytics", "distribution", key, lastFullYear],
    queryFn: ({ signal }) => fetchDistribution(key, "1991-01-01", `${lastFullYear}-12-31`, signal),
    enabled,
  });
  const occurrences = useQuery({
    queryKey: ["analytics", "occ-months", year, yesterday],
    queryFn: ({ signal }) =>
      fetchSeries(
        { dataset: "flood-occurrences", variable: "occurrences", start: `${year}-01-01`, end: yesterday, grain: "month", agg: "count" },
        signal,
      ),
  });

  if (!enabled) {
    return (
      <p role="status" className="rounded-lg border border-surface-border bg-surface p-4 text-sm">
        A reanálise do ponto central ainda está sendo carregada (um ponto a cada 2 minutos na
        primeira vez). As análises de chuva aparecem quando ela terminar.
      </p>
    );
  }

  const monthRows = (months.data?.points ?? []).map((p) => ({
    periodo: periodLabel(p.start, "month"),
    chuva: p.value,
    normal: p.reference,
    situacao: p.insufficient ? "dados insuficientes" : p.partial ? `parcial (${p.n} de ${p.expected} dias)` : "completo",
  }));
  const yearRows = (years.data?.points ?? []).map((p) => ({ ano: p.start.slice(0, 4), chuva: p.value, normal: p.reference }));
  const climRows = MONTHS_SHORT.map((label, i) => ({
    mes: label,
    reanalise: climReanalysis.data?.months[i]?.mean ?? null,
    faixa: [climReanalysis.data?.months[i]?.p25 ?? null, climReanalysis.data?.months[i]?.p75 ?? null],
    p25: climReanalysis.data?.months[i]?.p25 ?? null,
    p75: climReanalysis.data?.months[i]?.p75 ?? null,
    iag: climIag.data?.months[i]?.mean ?? null,
  }));
  const occByMonth = new Map((occurrences.data?.points ?? []).map((p) => [p.start, p.value]));
  const comboRows = (months.data?.points ?? []).map((p) => ({
    periodo: periodLabel(p.start, "month"),
    chuva: p.value,
    ocorrencias: occByMonth.get(p.start) ?? 0,
  }));
  const binRows = (distribution.data?.bins ?? []).map((b) => ({
    faixa: b.high >= 1000 ? `≥ ${formatNumber(b.low, 0)} mm` : `${formatNumber(b.low, 0)}–${formatNumber(b.high, 0)} mm`,
    dias: b.count,
  }));

  return (
    <div className="space-y-5">
      <p className="text-sm text-ink-muted">
        Ponto central da reanálise ({center.label}, {center.detail}). Tempo meteorológico é o que
        acontece em horas e dias; a normal de 30 anos descreve o clima.
      </p>

      {months.isPending ? (
        <Pending label="Carregando a chuva mensal…" />
      ) : (
        <ChartFrame
          id="chuva-mensal"
          title={`Chuva mês a mês em ${year} × normal 1991–2020`}
          summary="Barras: total de cada mês até ontem; linha: média do mesmo mês em 1991–2020 no mesmo ponto. Mês em andamento aparece como parcial."
          kind="MODELED"
          source="Open-Meteo (reanálise ERA5/ERA5-Land), CC BY 4.0"
          notes={[REANALYSIS_NOTE]}
          rows={monthRows}
          columns={[
            { key: "periodo", label: "Mês" },
            { key: "chuva", label: "Chuva", format: mm },
            { key: "normal", label: "Normal", format: mm },
            { key: "situacao", label: "Situação" },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={monthRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
              <XAxis dataKey="periodo" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={axisMm} tick={{ fontSize: 12 }} width={44} unit=" mm" />
              <Tooltip formatter={(v) => mm(Number(v))} />
              <Legend />
              <Bar dataKey="chuva" name="Chuva no mês" fill="#3a86b4" />
              <Line dataKey="normal" name="Normal 1991–2020" stroke="#14202b" strokeDasharray="4 3" dot />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}

      {climReanalysis.isPending || climIag.isPending ? (
        <Pending label="Carregando a sazonalidade…" />
      ) : (
        <ChartFrame
          id="sazonalidade"
          title="Sazonalidade: chuva média por mês (1991–2020)"
          summary="Linha azul e faixa: média e intervalo entre os percentis 25 e 75 da reanálise no ponto central. Linha escura: média medida pelo IAG/USP. As duas não são somadas: a diferença mostra o viés da reanálise."
          kind="MODELED"
          source="Open-Meteo (reanálise) e IAG/USP (medido)"
          rows={climRows}
          columns={[
            { key: "mes", label: "Mês" },
            { key: "reanalise", label: "Reanálise (média)", format: mm },
            { key: "p25", label: "Reanálise p25", format: mm },
            { key: "p75", label: "Reanálise p75", format: mm },
            { key: "iag", label: "IAG/USP medido (média)", format: mm },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={climRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
              <XAxis dataKey="mes" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={axisMm} tick={{ fontSize: 12 }} width={44} unit=" mm" />
              <Tooltip formatter={(v) => (Array.isArray(v) ? v.map((x) => mm(Number(x))).join(" a ") : mm(Number(v)))} />
              <Legend />
              <Area dataKey="faixa" name="Reanálise p25–p75" fill="#7fb3c9" stroke="none" fillOpacity={0.35} />
              <Line dataKey="reanalise" name="Reanálise (média)" stroke="#3a86b4" dot={false} />
              <Line dataKey="iag" name="IAG/USP medido (média)" stroke="#14202b" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}

      {years.isPending ? (
        <Pending label="Carregando os totais anuais…" />
      ) : (
        <ChartFrame
          id="chuva-anual"
          title={`Total anual de chuva, 1991–${lastFullYear}`}
          summary="Barras: total de cada ano no ponto central; linha: normal anual 1991–2020 do mesmo ponto. Variabilidade de um ano para outro não é tendência climática."
          kind="MODELED"
          source="Open-Meteo (reanálise ERA5/ERA5-Land), CC BY 4.0"
          notes={["Para uma série medida longa (desde 1933), veja a aba Tendências."]}
          rows={yearRows}
          columns={[
            { key: "ano", label: "Ano" },
            { key: "chuva", label: "Chuva", format: mm },
            { key: "normal", label: "Normal", format: mm },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={yearRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
              <XAxis dataKey="ano" tick={{ fontSize: 11 }} interval={4} />
              <YAxis tickFormatter={axisMm} tick={{ fontSize: 12 }} width={52} unit=" mm" />
              <Tooltip formatter={(v) => mm(Number(v))} />
              <Bar dataKey="chuva" name="Total anual" fill="#3a86b4" />
              <Line dataKey="normal" name="Normal 1991–2020" stroke="#14202b" strokeDasharray="4 3" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}

      {distribution.data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartFrame
            id="distribuicao"
            title={`Distribuição dos dias de chuva (1991–${lastFullYear})`}
            summary={`${distribution.data.wet_days} dias com 1 mm ou mais em ${distribution.data.days} dias, agrupados por volume diário.`}
            kind="MODELED"
            source="Open-Meteo (reanálise ERA5/ERA5-Land)"
            rows={binRows}
            columns={[
              { key: "faixa", label: "Chuva no dia" },
              { key: "dias", label: "Dias", format: (v) => num(v, 0) },
            ]}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={binRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
                <XAxis dataKey="faixa" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 12 }} width={48} />
                <Tooltip />
                <Bar dataKey="dias" name="Dias" fill="#1d4f91" />
              </BarChart>
            </ResponsiveContainer>
          </ChartFrame>
          <section aria-labelledby="extremos" className="space-y-2 rounded-lg border border-surface-border bg-surface p-4">
            <h3 id="extremos" className="font-semibold">
              10 maiores chuvas diárias (1991–{lastFullYear})
            </h3>
            <ol className="list-inside list-decimal text-sm tabular-nums">
              {distribution.data.extremes.map((e) => (
                <li key={e.day}>
                  {periodLabel(e.day, "day")}: {mm(e.value)}
                </li>
              ))}
            </ol>
            <p className="text-xs text-ink-muted">
              Valores da reanálise, que suaviza temporais: chuvas medidas em pluviômetros costumam
              ser maiores.
            </p>
          </section>
        </div>
      )}

      {months.data && occurrences.data && (
        <ChartFrame
          id="chuva-ocorrencias"
          title={`Chuva mensal × ocorrências registradas em ${year}`}
          summary="Barras: chuva do mês no ponto central (reanálise); linha: ocorrências de alagamento e inundação registradas em toda a cidade. Coincidência não prova causa: as ocorrências dependem de onde e quanto choveu e de como são registradas."
          kind="MODELED"
          source="Open-Meteo (reanálise) e GeoSampa (Defesa Civil/SIGRC)"
          notes={["Ocorrências: registros de atendimento publicados com atraso; o mês atual pode estar incompleto."]}
          rows={comboRows}
          columns={[
            { key: "periodo", label: "Mês" },
            { key: "chuva", label: "Chuva (centro)", format: mm },
            { key: "ocorrencias", label: "Ocorrências", format: (v) => num(v, 0) },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={comboRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
              <XAxis dataKey="periodo" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="mm" tickFormatter={axisMm} tick={{ fontSize: 12 }} width={44} unit=" mm" />
              <YAxis yAxisId="n" orientation="right" tick={{ fontSize: 12 }} width={40} />
              <Tooltip />
              <Legend />
              <Bar yAxisId="mm" dataKey="chuva" name="Chuva (mm)" fill="#3a86b4" />
              <Line yAxisId="n" dataKey="ocorrencias" name="Ocorrências" stroke="#c62828" />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}
    </div>
  );
}
