"use client";

import dynamic from "next/dynamic";
import { useReducedMotion, useWebGL } from "@/features/map/useCapabilities";
import { useState } from "react";
import { SimulationBanner } from "@/components/simulation/SimulationBanner";
import { useBasinBlock } from "@/features/geo/hooks";
import type { BasinLayerProps } from "@/features/geo/types";
import type { Feature, FeatureCollection } from "@/features/map/types";
import { CATEGORIES } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";
import { useRecentRuns } from "@/features/simulation/hooks";
import { formatDateTime } from "@/lib/format";
import { BasinBlock2D } from "./BasinBlock2D";

const BasinBlock3D = dynamic(() => import("./BasinBlock3D"), {
  ssr: false,
  loading: () => (
    <div role="status" className="h-[62vh] min-h-96 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">Carregando o bloco 3D…</span>
    </div>
  ),
});

type View = "3d" | "2d";

interface Props {
  basinId: number | null;
  simulationId: string | null;
  basins?: FeatureCollection<BasinLayerProps>;
  reservoirs?: FeatureCollection<Record<string, unknown>>;
  onSimulation: (id: string | null) => void;
}

/** Aba "Bloco 3D" (FR-128 a FR-131): escolha das cores (real ou simulação) e da vista 3D ou 2D. */
export function BasinBlockView({ basinId, simulationId, basins, reservoirs, onSimulation }: Props) {
  const block = useBasinBlock(basinId, simulationId);
  const recent = useRecentRuns();
  const webgl = useWebGL();
  const reducedMotion = useReducedMotion();
  const canUse3d = webgl !== false;
  // Sem WebGL ou com movimento reduzido, começa na versão 2D; a escolha da pessoa prevalece.
  const [chosenView, setView] = useState<View | null>(null);
  const view: View = chosenView ?? (webgl === false || reducedMotion ? "2d" : "3d");
  const [problem, setProblem] = useState<string | null>(null);

  if (basinId === null) {
    return (
      <p className="rounded-lg border border-dashed border-surface-border p-4 text-sm text-ink-muted">
        Escolha uma bacia no mapa ou no ranking da aba Bacias para ver o bloco 3D.
      </p>
    );
  }
  if (block.isPending) return <p className="text-sm text-ink-muted">Carregando a bacia…</p>;
  if (block.isError) {
    return (
      <p role="alert" className="text-sm">
        {block.error.message}
      </p>
    );
  }
  const data = block.data;
  const basinFeature = basins?.features.find((f) => f.properties.id === basinId) as Feature<BasinLayerProps> | undefined;
  const title = `${data.name} — ${data.source === "real" ? "estimativa real" : "simulação"}`;

  return (
    <section aria-labelledby="bloco-titulo" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="bloco-titulo" className="text-lg font-semibold">
            {data.name}
          </h2>
          <p className="text-sm text-ink-muted">
            Bacia principal: {data.main_basin ?? "—"} · {data.sectors.length} setores de risco ·{" "}
            {data.source === "real" ? "estimativa real" : "simulação"}
            {data.computed_at && ` de ${formatDateTime(data.computed_at)}`}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-ink-muted">
            Cores dos setores
            <select
              className="rounded-md border border-surface-border bg-surface px-2 py-1.5 text-sm text-ink"
              value={simulationId ?? ""}
              onChange={(e) => onSimulation(e.target.value || null)}
            >
              <option value="">Estimativa real (agora)</option>
              {simulationId && !recent.data?.some((r) => r.id === simulationId) && (
                <option value={simulationId}>Simulação do link</option>
              )}
              {(recent.data ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  Simulação: {r.scenario_text.slice(0, 70)}
                </option>
              ))}
            </select>
          </label>
          <div role="group" aria-label="Vista" className="flex gap-1">
            {(["3d", "2d"] as View[]).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                disabled={v === "3d" && !canUse3d}
                onClick={() => setView(v)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${view === v ? "bg-accent text-white" : "border border-surface-border"} disabled:opacity-50`}
              >
                {v === "3d" ? "3D" : "2D"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {data.banner && <SimulationBanner hybrid={/PREVIS[ÃA]O REAL/i.test(data.banner)} />}
      {!canUse3d && (
        <p role="status" className="text-sm text-ink-muted">
          Este navegador não tem WebGL: mostrando a versão em 2D, com as mesmas informações.
        </p>
      )}
      {problem && (
        <p role="status" className="text-sm text-amber-900">
          {problem}
        </p>
      )}

      {view === "3d" && canUse3d ? (
        <>
          <BasinBlock3D
            key={`${basinId}-${simulationId ?? "real"}`}
            block={data}
            basin={basinFeature}
            reservoirs={reservoirs}
            title={title}
            onError={setProblem}
          />
          <p className="text-xs text-ink-muted">
            Teclado: setas movem o mapa; Shift com as setas gira e inclina; + e − aproximam. A versão 2D traz a tabela dos
            setores.
          </p>
        </>
      ) : (
        <BasinBlock2D block={data} />
      )}

      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
        {(["CRITICAL", "HIGH", "MODERATE", "LOW", "UNKNOWN"] as RiskCategory[]).map((c) => (
          <span key={c} className="flex items-center gap-1">
            <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full" style={{ background: CATEGORIES[c].color }} />
            {CATEGORIES[c].label}
          </span>
        ))}
        <span>Linha azul: rio ou córrego a céu aberto · cinza: canalizado fechado · círculo verde-escuro: piscinão</span>
      </p>
      <p className="text-xs text-ink-muted">
        {data.disclaimer} Estimativa de risco experimental: não é alerta oficial. Em emergência, ligue 199 (Defesa Civil).
      </p>
    </section>
  );
}
