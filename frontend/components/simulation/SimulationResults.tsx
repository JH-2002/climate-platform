"use client";

import Link from "next/link";
import { basePath } from "@/lib/demo";
import { useState } from "react";
import { TerrainSection } from "@/components/geo/TerrainSection";
import { RiskBadge } from "@/components/risk/RiskBadge";
import { CATEGORIES, CATEGORY_ORDER, RAIN_LEVEL_LABELS, SUSCEPTIBILITY_LABELS, titleCase } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import { formatPercent, simulationHref } from "@/features/simulation/scenario";
import type { RepeatCheck, RunListItem, SimulatedSector, SimulationRun } from "@/features/simulation/types";
import { formatDateTime, formatNumber } from "@/lib/format";

/** Resumo do resultado (FR-107) e comparação com a estimativa real (FR-106). */
export function SimulationSummary(props: { run: SimulationRun; onRepeat?: () => void; repeating?: boolean }) {
  const { run, onRepeat, repeating = false } = props;
  const [copied, setCopied] = useState(false);
  const c = run.comparison;
  const highNow = run.counts.HIGH + run.counts.CRITICAL;
  const highReal = c.real_counts.HIGH + c.real_counts.CRITICAL;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${basePath()}${simulationHref(run.id)}`);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section aria-labelledby="resultado-titulo" className="space-y-4 rounded-lg border border-violet-300 bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="resultado-titulo" className="text-lg font-semibold">
            Resultado da simulação
          </h2>
          <p className="text-sm">{run.scenario_text}.</p>
          <p className="text-xs text-ink-muted">
            Executada em {formatDateTime(run.created_at)} · motor de simulação {run.simulation_engine_version} · motor de
            risco {run.risk_engine_version} · {run.sector_count} setores · {run.duration_ms} ms
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {onRepeat && (
            <button
              type="button"
              onClick={onRepeat}
              disabled={repeating}
              className="rounded-md border border-violet-700 px-3 py-1.5 text-sm font-medium text-violet-800 hover:bg-violet-700 hover:text-white disabled:opacity-50"
            >
              {repeating ? "Repetindo…" : run.seed !== null ? `Repetir (seed ${run.seed})` : "Repetir"}
            </button>
          )}
          <button
            type="button"
            onClick={() => void copyLink()}
            className="rounded-md border border-violet-700 px-3 py-1.5 text-sm font-medium text-violet-800 hover:bg-violet-700 hover:text-white"
          >
            {copied ? "Link copiado" : "Copiar link"}
          </button>
        </div>
      </div>
      {run.mode === "HYBRID" && (
        <p className="text-sm">
          Partiu da previsão real
          {run.forecast_issued_at ? ` emitida em ${formatDateTime(run.forecast_issued_at)}` : ""} (Open-Meteo.com, CC BY
          4.0), com a chuva das 72 h anteriores real. Setores sem ponto de previsão por perto ficam como desconhecido.
        </p>
      )}
      {run.repeat_check && <RepeatNote check={run.repeat_check} />}
      {run.sectors_changed && (
        <p role="status" className="rounded-md bg-amber-50 p-2 text-sm">
          Os dados dos setores mudaram desde esta simulação (sincronização diária do GeoSampa). Simular de novo pode dar
          outro resultado.
        </p>
      )}

      <ul className="grid grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))] gap-2" aria-label="Setores por categoria na simulação">
        {CATEGORY_ORDER.map((cat) => (
          <li key={cat} className="rounded-md border border-surface-border p-2">
            <RiskBadge category={cat} />
            <p className="mt-1 text-2xl font-semibold tabular-nums">{run.counts[cat]}</p>
            <p className="text-xs text-ink-muted">agora no real: {c.real_run ? c.real_counts[cat] : "—"}</p>
          </li>
        ))}
      </ul>

      {run.ensemble && (
        <div className="rounded-md bg-violet-50 p-3 text-sm">
          <h3 className="font-medium">Incerteza: {run.ensemble.members} variações (seed {run.seed})</h3>
          <p>
            Setores em alto ou crítico: em média <strong>{formatNumber(run.ensemble.mean)}</strong>; em 80% das
            variações, entre {formatNumber(run.ensemble.p10, 0)} e {formatNumber(run.ensemble.p90, 0)} (mínimo{" "}
            {run.ensemble.minimum}, máximo {run.ensemble.maximum}). As categorias acima são do cenário central; a
            tabela mostra a probabilidade de cada setor chegar a alto ou crítico.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <h3 className="font-medium">Comparação com a estimativa real</h3>
        {c.real_run === null ? (
          <p className="text-sm text-ink-muted">Ainda não há estimativa real para comparar.</p>
        ) : (
          <>
            <p className="text-sm">
              Setores em alto ou crítico: <strong>{highNow}</strong> na simulação, {highReal} na estimativa real de{" "}
              {formatDateTime(c.real_run.computed_at)}. {c.raised} setores sobem de categoria, {c.lowered} descem e{" "}
              {c.unchanged} ficam iguais.
              {c.not_comparable > 0 && ` ${c.not_comparable} estavam como desconhecido no real e não são comparados.`}
            </p>
            {c.real_run.stale && (
              <p className="text-sm text-amber-900">A estimativa real está desatualizada: compare com cuidado.</p>
            )}
            {c.subprefectures.length > 0 && (
              <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Comparação com a estimativa real">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Subprefeituras mais afetadas na simulação</caption>
                  <thead className="text-ink-muted">
                    <tr>
                      <th scope="col" className="py-1 pr-3 font-medium">Subprefeitura</th>
                      <th scope="col" className="py-1 pr-3 text-right font-medium">Alto + crítico (simulação)</th>
                      <th scope="col" className="py-1 pr-3 text-right font-medium">Alto + crítico (real)</th>
                      <th scope="col" className="py-1 pr-3 text-right font-medium">Sobem</th>
                      <th scope="col" className="py-1 text-right font-medium">Setores</th>
                    </tr>
                  </thead>
                  <tbody>
                    {c.subprefectures.map((s) => (
                      <tr key={s.name} className="border-t border-surface-border">
                        <th scope="row" className="py-1 pr-3 font-normal">{titleCase(s.name)}</th>
                        <td className="py-1 pr-3 text-right tabular-nums">{s.high_or_above_simulated}</td>
                        <td className="py-1 pr-3 text-right tabular-nums">{s.high_or_above_real}</td>
                        <td className="py-1 pr-3 text-right tabular-nums">{s.raised}</td>
                        <td className="py-1 text-right tabular-nums">{s.sectors}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function RepeatNote({ check }: { check: RepeatCheck }) {
  const reasons = [
    !check.same_engine_versions && "a versão do motor mudou",
    !check.same_sectors && "os dados dos setores mudaram",
    check.same_forecast === false && "a previsão real foi atualizada",
  ].filter(Boolean);
  return (
    <p role="status" className={`rounded-md p-2 text-sm ${check.identical_results ? "bg-emerald-50" : "bg-amber-50"}`}>
      Repetição de{" "}
      <Link className="font-medium underline" href={simulationHref(check.original_id)}>
        uma simulação anterior
      </Link>
      :{" "}
      {check.identical_results
        ? "resultado idêntico, setor por setor."
        : `resultado diferente${reasons.length ? ` porque ${reasons.join(", ")}` : ""}.`}
    </p>
  );
}

function RealBadge({ category }: { category: RiskCategory | null }) {
  if (category === null) return <span className="text-ink-muted">—</span>;
  return <span className="text-sm">{CATEGORIES[category].label}</span>;
}

/** Ranking dos setores simulados, do maior para o menor risco. */
export function SimulatedSectorTable(props: {
  items: SimulatedSector[];
  total: number;
  selectedId: number | null;
  onSelect: (id: number) => void;
  limit?: number;
  withProbability?: boolean;
}) {
  const { items, total, selectedId, onSelect, limit = 50, withProbability = false } = props;
  const shownItems = items.slice(0, limit);
  return (
    <div className="overflow-x-auto rounded-lg border border-surface-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Setores simulados">
      <table className="w-full border-collapse bg-surface text-left text-sm">
        <caption className="bg-violet-50 px-4 py-2 text-left font-medium">
          Setores na simulação ({shownItems.length < total ? `${shownItems.length} de ${total}` : total}) — cenário hipotético
        </caption>
        <thead className="text-ink-muted">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Setor</th>
            <th scope="col" className="px-4 py-2 font-medium">Subprefeitura</th>
            <th scope="col" className="px-4 py-2 font-medium">Na simulação</th>
            {withProbability && (
              <th scope="col" className="px-4 py-2 text-right font-medium">Chance de alto ou crítico</th>
            )}
            <th scope="col" className="px-4 py-2 font-medium">Real agora</th>
            <th scope="col" className="px-4 py-2 font-medium">Chuva no cenário</th>
            <th scope="col" className="px-4 py-2 font-medium">Suscetibilidade</th>
            <th scope="col" className="px-4 py-2 font-medium">
              <span className="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {shownItems.map((s) => (
            <tr key={s.id} className={`border-t border-surface-border ${selectedId === s.id ? "bg-surface-muted" : ""}`}>
              <th scope="row" className="px-4 py-2 font-medium">
                {s.code}
                <span className="block text-xs font-normal text-ink-muted">{titleCase(s.name)}</span>
              </th>
              <td className="px-4 py-2">{titleCase(s.subprefecture)}</td>
              <td className="px-4 py-2">
                <RiskBadge category={s.category} />
              </td>
              {withProbability && (
                <td className="px-4 py-2 text-right tabular-nums">
                  {formatPercent(s.p_high)}
                  {s.p_critical !== null && s.p_critical > 0 && (
                    <span className="block text-xs text-ink-muted">crítico: {formatPercent(s.p_critical)}</span>
                  )}
                </td>
              )}
              <td className="px-4 py-2">
                <RealBadge category={s.real_category} />
              </td>
              <td className="px-4 py-2">
                {s.rain_level === null ? "—" : RAIN_LEVEL_LABELS[s.rain_level]}
                <span className="block text-xs text-ink-muted tabular-nums">
                  máx. {formatNumber(s.p1h_max_mm)} mm/h · {formatNumber(s.p24_mm)} mm
                </span>
              </td>
              <td className="px-4 py-2">
                {SUSCEPTIBILITY_LABELS[s.susceptibility]} <span className="text-ink-muted">(R{s.grade})</span>
              </td>
              <td className="px-4 py-2">
                <button
                  type="button"
                  onClick={() => onSelect(s.id)}
                  className="rounded-md border border-violet-700 px-2 py-1 text-xs font-medium text-violet-800 hover:bg-violet-700 hover:text-white"
                >
                  Por quê?<span className="sr-only"> Explicação do setor {s.code} na simulação</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Explicação de um setor simulado: os mesmos fatores do motor real, com a chuva do cenário. */
export function SimulatedSectorExplanation({ sector, onClose }: { sector: SimulatedSector; onClose: () => void }) {
  return (
    <section aria-labelledby="setor-sim-titulo" className="space-y-3 rounded-lg border border-violet-300 bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="setor-sim-titulo" className="text-lg font-semibold">
            Setor {sector.code} — {titleCase(sector.name)}
          </h2>
          <p className="text-sm text-ink-muted">
            {titleCase(sector.subprefecture)} · grau R{sector.grade}
            {sector.households !== null && ` · ${sector.households} moradias`}
          </p>
        </div>
        <button type="button" onClick={onClose} className="rounded-md border border-surface-border px-3 py-1 text-sm">
          Fechar
        </button>
      </div>
      <p className="flex flex-wrap items-center gap-2 text-sm">
        Na simulação: <RiskBadge category={sector.category} size="lg" />
        <span className="text-ink-muted">· real agora: {sector.real_category ? CATEGORIES[sector.real_category].label : "—"}</span>
      </p>
      {sector.p_high !== null && (
        <p className="text-sm">
          Entre as variações: chega a alto ou crítico em {formatPercent(sector.p_high)} delas
          {sector.p_critical !== null && ` (crítico em ${formatPercent(sector.p_critical)})`}.
        </p>
      )}
      <p className="text-sm">
        Chuva do cenário neste setor: até {formatNumber(sector.p1h_max_mm)} mm em 1 h e {formatNumber(sector.p24_mm)} mm no
        total ({formatNumber(sector.rain_factor * 100, 0)}% da chuva do cenário
        {sector.distance_km !== null && `, a ${formatNumber(sector.distance_km)} km do centro da célula`}).
      </p>
      <ul className="space-y-1 text-sm">
        {sector.factors.map((f) => (
          <li key={f.code} className="flex gap-2">
            <span aria-hidden="true">{f.effect === "raises" ? "▲" : "•"}</span>
            <span>
              {f.text}
              {f.effect === "raises" && <span className="sr-only"> (aumenta o risco)</span>}
            </span>
          </li>
        ))}
      </ul>
      <TerrainSection sectorId={sector.id} />
    </section>
  );
}

/** Histórico das simulações recentes (FR-110). */
export function RecentRuns({ items, currentId }: { items: RunListItem[]; currentId: string | null }) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="historico-titulo" className="space-y-2 rounded-lg border border-surface-border bg-surface p-4">
      <h2 id="historico-titulo" className="text-lg font-semibold">
        Simulações recentes
      </h2>
      <ul className="divide-y divide-surface-border text-sm">
        {items.map((r) => (
          <li key={r.id} className="py-2">
            <Link
              href={simulationHref(r.id)}
              aria-current={r.id === currentId ? "page" : undefined}
              className={`font-medium underline ${r.id === currentId ? "text-ink" : "text-violet-800"}`}
            >
              {r.scenario_text}
            </Link>
            <span className="block text-xs text-ink-muted">
              {formatDateTime(r.created_at)} · {r.mode === "HYBRID" ? "a partir da previsão real" : "só o cenário"} ·{" "}
              {r.high_or_above} setores em alto ou crítico
              {r.unknown > 0 && ` · ${r.unknown} desconhecidos`}
              {r.seed !== null && ` · seed ${r.seed}`}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
