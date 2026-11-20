"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { InsightList } from "@/components/overview/InsightList";
import { KpiGrid } from "@/components/overview/KpiGrid";
import { WhereSection } from "@/components/overview/WhereSection";
import { NowCard } from "@/components/weather/NowCard";
import { useInsights, useKpis } from "@/features/analytics/hooks";
import { fetchOccurrencesLayer, fetchRiskAreas } from "@/features/risk/api";
import { useForecast } from "@/features/weather/hooks";

// Praça da Sé: referência para "agora" na visão geral; o painel do clima permite escolher o local.
const CENTER = { lat: -23.5505, lon: -46.6333 };

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <div role="status" className="h-24 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">{label}</span>
    </div>
  );
}

/** Painel executivo (spec 006, FR-086): agora, atenção, onde e confiabilidade. */
export default function OverviewPage() {
  const kpis = useKpis();
  const insights = useInsights();
  const forecast = useForecast(CENTER.lat, CENTER.lon);
  const topRisk = useQuery({
    queryKey: ["overview", "top-risk"],
    queryFn: ({ signal }) => fetchRiskAreas({ category: null, subprefecture: null, sectorId: null }, signal),
    select: (page) => page.items.slice(0, 5),
    refetchInterval: 10 * 60_000,
  });
  const occurrences = useQuery({
    queryKey: ["map", "occurrences"],
    queryFn: ({ signal }) => fetchOccurrencesLayer(signal),
    staleTime: 60 * 60_000,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Visão geral</h1>
        <p className="text-sm text-ink-muted">
          Município de São Paulo. Cada número mostra a fonte e o tipo: medido, modelo, previsão
          ou calculado pelo sistema.
        </p>
      </header>

      <Section id="agora-secao" title="O que está acontecendo">
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-1">
            {forecast.data ? <NowCard now={forecast.data.now} /> : <Loading label="Carregando a estimativa para agora…" />}
            <p className="mt-1 text-xs text-ink-muted">
              Centro (Sé).{" "}
              <Link className="text-accent underline" href="/weather">
                Escolher outro local
              </Link>
            </p>
          </div>
          <div className="lg:col-span-2">
            {kpis.isPending && <Loading label="Carregando os indicadores…" />}
            {kpis.isError && (
              <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
                Não foi possível carregar os indicadores. {kpis.error.message}
              </p>
            )}
            {kpis.data && <KpiGrid items={kpis.data.items} />}
          </div>
        </div>
      </Section>

      <Section id="atencao-secao" title="O que merece atenção">
        {insights.isPending && <Loading label="Avaliando as regras…" />}
        {insights.isError && (
          <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
            Não foi possível avaliar as regras. {insights.error.message}
          </p>
        )}
        {insights.data && (
          <InsightList
            items={insights.data.items}
            notes={insights.data.notes}
            rulesVersion={insights.data.rules_version}
          />
        )}
      </Section>

      <Section id="onde-secao" title="Onde">
        <WhereSection areas={topRisk.data} occurrences={occurrences.data} />
      </Section>

      <p className="text-xs text-ink-muted">
        Para avisos oficiais, acompanhe a Defesa Civil (199) e o CGE. Estado detalhado das fontes e
        da infraestrutura em{" "}
        <Link className="text-accent underline" href="/status">
          Estado do sistema
        </Link>
        .
      </p>
    </div>
  );
}
