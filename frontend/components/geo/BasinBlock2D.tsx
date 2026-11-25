"use client";

import { RiskBadge } from "@/components/risk/RiskBadge";
import { reliefUrl } from "@/features/geo/api";
import { formatPercent } from "@/features/simulation/scenario";
import type { BasinBlock } from "@/features/geo/types";
import { titleCase } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import { formatNumber } from "@/lib/format";

const KNOWN: readonly string[] = ["LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"];

/** Contagem de setores por categoria, em texto: base do texto alternativo e da legenda. */
export function categorySummary(block: BasinBlock): string {
  const counts = new Map<string, number>();
  for (const s of block.sectors) counts.set(s.category, (counts.get(s.category) ?? 0) + 1);
  const labels: Record<string, string> = {
    CRITICAL: "crítico",
    HIGH: "alto",
    MODERATE: "moderado",
    LOW: "baixo",
    UNKNOWN: "desconhecido",
  };
  const parts = ["CRITICAL", "HIGH", "MODERATE", "LOW", "UNKNOWN"]
    .filter((c) => counts.get(c))
    .map((c) => `${counts.get(c)} ${labels[c]}`);
  return parts.length ? parts.join(", ") : "nenhum setor de risco";
}

/**
 * Alternativa em 2D do bloco (FR-131): relevo sombreado gerado no servidor, com os mesmos setores,
 * drenagem e piscinões, e a tabela. Funciona sem WebGL.
 */
export function BasinBlock2D({ block }: { block: BasinBlock }) {
  const elevation =
    block.elev_min_m !== null && block.elev_max_m !== null
      ? `de ${formatNumber(block.elev_min_m, 0)} a ${formatNumber(block.elev_max_m, 0)} m`
      : "sem dado de elevação";
  const withChance = block.sectors.some((s) => s.p_high !== null);
  return (
    <div className="space-y-3">
      <figure className="space-y-1">
        {/* eslint-disable-next-line @next/next/no-img-element -- imagem gerada pela API, sem otimização */}
        <img
          src={reliefUrl(block.basin_id, block.simulation_id)}
          alt={`Relevo sombreado da bacia ${block.name}, elevação ${elevation}. Setores de risco (${block.sectors.length}): ${categorySummary(block)}. Linhas azuis: rios e córregos a céu aberto; cinza: canalizados fechados; verde-escuro: piscinões.`}
          className="w-full rounded-lg border border-surface-border"
        />
        <figcaption className="text-xs text-ink-muted">
          Relevo sombreado ({elevation}); fora da bacia, esmaecido. Cores dos setores:{" "}
          {block.source === "real" ? "estimativa real mais recente" : "simulação"}. Relevo: Copernicus DEM GLO-30;{" "}
          {block.hydro_attribution}.
        </figcaption>
      </figure>
      <div className="overflow-x-auto rounded-lg border border-surface-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Setores do bloco">
        <table className="w-full border-collapse bg-surface text-left text-sm">
          <caption className="px-3 py-2 text-left font-medium">
            Setores de risco na bacia ({block.sectors.length}) — {block.source === "real" ? "estimativa real" : "simulação"}
          </caption>
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="px-3 py-1 font-medium">Setor</th>
              <th scope="col" className="px-3 py-1 font-medium">Grau</th>
              <th scope="col" className="px-3 py-1 font-medium">Categoria</th>
              {withChance && (
                <th scope="col" className="px-3 py-1 text-right font-medium">Chance de alto ou crítico</th>
              )}
            </tr>
          </thead>
          <tbody>
            {block.sectors.map((s) => (
              <tr key={s.id} className="border-t border-surface-border">
                <th scope="row" className="px-3 py-1 font-medium">
                  {s.code}
                  <span className="block text-xs font-normal text-ink-muted">{titleCase(s.name)}</span>
                </th>
                <td className="px-3 py-1">R{s.grade}</td>
                <td className="px-3 py-1">
                  {KNOWN.includes(s.category) ? <RiskBadge category={s.category as RiskCategory} /> : s.category}
                </td>
                {withChance && <td className="px-3 py-1 text-right tabular-nums">{formatPercent(s.p_high)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
