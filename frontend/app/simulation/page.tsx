"use client";

import dynamic from "next/dynamic";
import { Suspense, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ScenarioForm } from "@/components/simulation/ScenarioForm";
import { SimulationBanner } from "@/components/simulation/SimulationBanner";
import {
  SimulatedSectorExplanation,
  SimulatedSectorTable,
  SimulationSummary,
} from "@/components/simulation/SimulationResults";
import { useLocations } from "@/features/locations/useLocations";
import {
  useCenters,
  usePresets,
  useRunSimulation,
  useSimulatedSector,
  useSimulatedSectors,
  useSimulation,
  useSimulationLayer,
} from "@/features/simulation/hooks";
import { parseSimulationState, serializeSimulationState, type SimulationState } from "@/features/simulation/scenario";
import type { ScenarioInput } from "@/features/simulation/types";

// A biblioteca de mapa só é carregada nesta página e só no navegador.
const SimulationMap = dynamic(() => import("@/components/simulation/SimulationMap"), {
  ssr: false,
  loading: () => (
    <div role="status" className="h-[55vh] min-h-80 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">Carregando o mapa…</span>
    </div>
  ),
});

function SimulationPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const fromUrl = parseSimulationState(params);
  const [form, setForm] = useState<{ scenario: ScenarioInput; preset: string | null }>({
    scenario: fromUrl.scenario,
    preset: fromUrl.preset,
  });
  const presets = usePresets();
  const centers = useCenters();
  const { locations } = useLocations();
  const mutation = useRunSimulation();
  const run = useSimulation(fromUrl.runId);
  const sectors = useSimulatedSectors(fromUrl.runId);
  const layer = useSimulationLayer(fromUrl.runId);
  const detail = useSimulatedSector(fromUrl.runId, fromUrl.sectorId);
  const results = useRef<HTMLDivElement>(null);

  // Link só com a execução: o formulário assume o cenário gravado.
  const hasScenarioInUrl = params.has("total");
  useEffect(() => {
    if (run.data && !hasScenarioInUrl) setForm({ scenario: run.data.scenario, preset: run.data.preset });
  }, [run.data, hasScenarioInUrl]);

  function navigate(next: SimulationState) {
    router.replace(`${pathname}?${serializeSimulationState(next)}`, { scroll: false });
  }

  function submit() {
    mutation.mutate(
      { scenario: form.scenario, preset: form.preset },
      {
        onSuccess: (created) => {
          navigate({ ...form, runId: created.id, sectorId: null });
          results.current?.focus();
        },
      },
    );
  }

  const state: SimulationState = { ...fromUrl, scenario: form.scenario, preset: form.preset };
  const runError = run.isError
    ? "status" in run.error && run.error.status === 404
      ? "Simulação não encontrada. As simulações ficam guardadas por 30 dias."
      : `Não foi possível carregar a simulação. ${run.error.message}`
    : null;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Laboratório de simulação</h1>
        <p className="text-sm text-ink-muted">
          Monte um cenário de chuva e veja o que o motor de risco estimaria para cada setor de risco hidrológico da
          Prefeitura, comparando com a estimativa real de agora. Nada daqui entra nas outras páginas.
        </p>
      </header>

      <SimulationBanner />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <ScenarioForm
          scenario={form.scenario}
          preset={form.preset}
          presets={presets.data ?? []}
          centers={centers.data ?? []}
          locations={locations}
          pending={mutation.isPending}
          error={mutation.isError ? mutation.error.message : null}
          onChange={(scenario, preset) => setForm({ scenario, preset })}
          onSubmit={submit}
        />
        <SimulationMap
          layer={layer.data}
          cell={form.scenario.cell}
          onPickCenter={(latitude, longitude) =>
            setForm((f) => (f.scenario.cell ? { preset: null, scenario: { ...f.scenario, cell: { ...f.scenario.cell, latitude, longitude } } } : f))
          }
          onSelectSector={(sectorId) => navigate({ ...state, sectorId })}
        />
      </div>

      <div ref={results} tabIndex={-1} className="space-y-5 outline-none">
        {runError && (
          <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
            {runError}
          </p>
        )}
        {fromUrl.runId && run.isPending && (
          <div role="status" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
            <span className="sr-only">Carregando o resultado…</span>
          </div>
        )}
        {run.data && (
          <>
            <SimulationBanner hybrid={run.data.mode === "HYBRID"} />
            <SimulationSummary run={run.data} />
            {detail.data && (
              <SimulatedSectorExplanation sector={detail.data} onClose={() => navigate({ ...state, sectorId: null })} />
            )}
            {sectors.data && (
              <SimulatedSectorTable
                items={sectors.data.items}
                total={sectors.data.total}
                selectedId={fromUrl.sectorId}
                onSelect={(sectorId) => {
                  navigate({ ...state, sectorId });
                  window.scrollTo({ top: results.current?.offsetTop ?? 0, behavior: "smooth" });
                }}
              />
            )}
          </>
        )}
        {!fromUrl.runId && (
          <p className="rounded-lg border border-dashed border-surface-border p-4 text-sm text-ink-muted">
            Escolha um cenário pronto ou ajuste os valores e clique em “Simular”. O resultado ganha um link próprio, que
            fica guardado por 30 dias.
          </p>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <SimulationPage />
    </Suspense>
  );
}
