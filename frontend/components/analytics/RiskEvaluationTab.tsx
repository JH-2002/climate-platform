"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchRiskEvaluation } from "@/features/analytics/api";
import { pct } from "@/features/analytics/format";
import {
  calibrationSentence,
  detectionSentence,
  falseAlarmSentence,
  monthLabel,
  periodSentence,
} from "@/features/analytics/riskEvaluation";
import type { ContingencyTable } from "@/features/analytics/types";
import { CATEGORIES, titleCase } from "@/features/risk/categories";
import { formatDateTime, formatNumber } from "@/lib/format";
import { ChartFrame } from "./ChartFrame";

const METRICS: { key: keyof ContingencyTable; label: string; help: string }[] = [
  { key: "pod", label: "Taxa de detecção", help: "Dos dias-subprefeitura com ocorrência, quantos o sistema marcou como alto ou crítico. Quanto maior, melhor." },
  { key: "far", label: "Alarmes falsos", help: "Dos dias marcados como alto ou crítico, quantos ficaram sem ocorrência registrada. Quanto menor, melhor." },
  { key: "csi", label: "Índice de sucesso crítico", help: "Acertos sobre acertos, falhas e alarmes falsos juntos. Resume os dois anteriores; quanto maior, melhor." },
  { key: "bias", label: "Viés de frequência", help: "Dias marcados sobre dias com ocorrência. 1 = marca na mesma frequência; acima de 1, marca demais." },
  { key: "base_rate", label: "Frequência das ocorrências", help: "Quantos dias-subprefeitura tiveram ocorrência registrada. Mostra o quanto o evento é raro." },
];

function metricValue(key: keyof ContingencyTable, value: number | null): string {
  if (key === "bias") return value === null ? "—" : formatNumber(value, 2);
  return pct(value);
}

/** Aba "Avaliação do risco" (spec 015, FR-216): retroteste do motor contra ocorrências registradas. */
export function RiskEvaluationTab() {
  const evaluation = useQuery({
    queryKey: ["analytics", "risk-evaluation"],
    queryFn: ({ signal }) => fetchRiskEvaluation(signal),
    retry: false,
  });
  if (evaluation.isPending) {
    return (
      <div role="status" className="h-60 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
        <span className="sr-only">Carregando a avaliação do motor…</span>
      </div>
    );
  }
  if (evaluation.isError) return <p role="alert" className="text-sm">{evaluation.error.message}</p>;
  const data = evaluation.data;
  const table = data.contingency;
  const reliabilityRows = data.reliability.map((r) => ({
    categoria: CATEGORIES[r.category].label,
    dias: r.units,
    com: r.with_occurrence,
    taxa: r.rate === null ? null : Math.round(r.rate * 1000) / 10,
  }));
  const calibrationRows = data.calibration.map((r) => ({
    fator: formatNumber(r.factor, 1),
    csi: r.csi === null ? null : Math.round(r.csi * 1000) / 10,
    pod: r.pod === null ? null : Math.round(r.pod * 1000) / 10,
    far: r.far === null ? null : Math.round(r.far * 1000) / 10,
  }));
  const monthlyRows = data.monthly.map((m) => ({
    mes: monthLabel(m.month),
    ocorrencias: m.events,
    acertos: m.hits,
    alarmes: m.false_alarms,
    pod: pct(m.pod),
    csi: pct(m.csi),
  }));
  const percent = (v: unknown) => (typeof v === "number" ? `${formatNumber(v, 1)}%` : "—");

  return (
    <div className="space-y-5">
      <aside role="note" className="rounded-lg border-l-4 border-status-warn bg-amber-50 p-3 text-sm">
        Retroteste do motor experimental: para cada dia passado, o motor rodou com a chuva <strong>prevista</strong> arquivada
        (primeiras horas de cada rodada do modelo, melhor do que a previsão de véspera usada ao vivo) e o resultado foi comparado
        com as ocorrências registradas pela Prefeitura, por subprefeitura e dia. Ocorrência registrada é só parte dos alagamentos
        reais. Estes números medem o motor; não são garantia de acerto.
      </aside>

      <section aria-labelledby="avaliacao-resumo" className="space-y-3 rounded-lg border border-surface-border bg-surface p-4 text-sm">
        <h3 id="avaliacao-resumo" className="font-semibold">Resumo</h3>
        <p>{periodSentence(data)}</p>
        <p>{detectionSentence(table)}</p>
        <p>{falseAlarmSentence(table)}</p>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {METRICS.map((m) => (
            <div key={m.key} className="rounded-md border border-surface-border p-3">
              <dt className="text-xs text-ink-muted">{m.label}</dt>
              <dd className="text-xl font-semibold tabular-nums">{metricValue(m.key, table[m.key] as number | null)}</dd>
              <dd className="mt-1 text-xs text-ink-muted">{m.help}</dd>
            </div>
          ))}
        </dl>
        <table className="w-full max-w-lg border-collapse text-left text-sm">
          <caption className="mb-1 text-left text-xs text-ink-muted">
            Dias-subprefeitura: o sistema marcou alto ou crítico? Houve ocorrência registrada?
          </caption>
          <thead>
            <tr className="text-ink-muted">
              <td />
              <th scope="col" className="py-1 pr-3 font-medium">Com ocorrência</th>
              <th scope="col" className="py-1 font-medium">Sem ocorrência</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            <tr className="border-t border-surface-border">
              <th scope="row" className="py-1 pr-3 font-medium">Marcado (alto ou crítico)</th>
              <td className="py-1 pr-3">{table.hits} acertos</td>
              <td className="py-1">{table.false_alarms} alarmes falsos</td>
            </tr>
            <tr className="border-t border-surface-border">
              <th scope="row" className="py-1 pr-3 font-medium">Não marcado</th>
              <td className="py-1 pr-3">{table.misses} falhas</td>
              <td className="py-1">{table.correct_negatives} negativos corretos</td>
            </tr>
          </tbody>
        </table>
      </section>

      <ChartFrame
        id="avaliacao-confiabilidade"
        title="Ocorrências por categoria estimada"
        summary="Para cada categoria máxima do dia na subprefeitura, a parte dos dias que teve ocorrência registrada. Numa estimativa útil, a parte cresce de baixo para crítico."
        kind="DERIVED"
        source={data.sources.join(" · ")}
        rows={reliabilityRows}
        columns={[
          { key: "categoria", label: "Categoria máxima" },
          { key: "dias", label: "Dias-subprefeitura" },
          { key: "com", label: "Com ocorrência" },
          { key: "taxa", label: "Parte com ocorrência", format: percent },
        ]}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={reliabilityRows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
            <XAxis dataKey="categoria" tick={{ fontSize: 12 }} />
            <YAxis unit="%" tick={{ fontSize: 12 }} width={48} />
            <Tooltip formatter={(v) => percent(v)} />
            <Bar dataKey="taxa" name="Parte com ocorrência" fill="#0b5c7a" />
          </BarChart>
        </ResponsiveContainer>
      </ChartFrame>

      <ChartFrame
        id="avaliacao-calibracao"
        title="Calibração das faixas de chuva"
        summary={calibrationSentence(data)}
        kind="DERIVED"
        source="Mesmo retroteste com as faixas de 1 h e 24 h multiplicadas por fatores de 0,3 a 1,5"
        notes={[
          `Faixas atuais (fator 1,0): ${data.current_thresholds.p1h_mm.join(", ")} mm em 1 h e ${data.current_thresholds.p24_mm.join(", ")} mm em 24 h.`,
        ]}
        rows={calibrationRows}
        columns={[
          { key: "fator", label: "Fator" },
          { key: "csi", label: "Sucesso crítico", format: percent },
          { key: "pod", label: "Detecção", format: percent },
          { key: "far", label: "Alarmes falsos", format: percent },
        ]}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={calibrationRows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
            <XAxis dataKey="fator" tick={{ fontSize: 12 }} />
            <YAxis unit="%" tick={{ fontSize: 12 }} width={48} domain={[0, 100]} />
            <Tooltip formatter={(v) => percent(v)} />
            <Legend />
            <ReferenceLine x="1,0" stroke="#6b7280" strokeDasharray="4 4" label={{ value: "atual", fontSize: 11 }} />
            <Line dataKey="csi" name="Sucesso crítico" stroke="#0b5c7a" strokeWidth={2} dot />
            <Line dataKey="pod" name="Detecção" stroke="#15803d" dot={false} />
            <Line dataKey="far" name="Alarmes falsos" stroke="#b91c1c" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>

      <ChartFrame
        id="avaliacao-mes"
        title="Mês a mês"
        summary="Dias-subprefeitura com ocorrência registrada e quantos deles o sistema marcou como alto ou crítico, por mês."
        kind="DERIVED"
        source={data.sources.join(" · ")}
        rows={monthlyRows}
        columns={[
          { key: "mes", label: "Mês" },
          { key: "ocorrencias", label: "Com ocorrência" },
          { key: "acertos", label: "Acertos" },
          { key: "alarmes", label: "Alarmes falsos" },
          { key: "pod", label: "Detecção" },
          { key: "csi", label: "Sucesso crítico" },
        ]}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={monthlyRows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dde3e8" />
            <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={40} />
            <Tooltip />
            <Legend />
            <Bar dataKey="ocorrencias" name="Com ocorrência" fill="#94a3b8" />
            <Bar dataKey="acertos" name="Acertos" fill="#0b5c7a" />
          </BarChart>
        </ResponsiveContainer>
      </ChartFrame>

      {data.unmatched_subprefectures.length > 0 && (
        <p className="text-xs text-ink-muted">
          Ocorrências em subprefeituras sem setor mapeado ficaram de fora:{" "}
          {data.unmatched_subprefectures.map(titleCase).join(", ")}.
        </p>
      )}
      <p className="text-xs text-ink-muted">
        Motor {data.engine_version} · avaliação calculada em {formatDateTime(data.computed_at)} · recalculada uma vez por dia.
      </p>
    </div>
  );
}
