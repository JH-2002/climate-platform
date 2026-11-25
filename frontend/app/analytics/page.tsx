"use client";

import Link from "next/link";
import { ReportShortcut } from "@/components/reports/ReportShortcut";
import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { RainTab } from "@/components/analytics/RainTab";
import { RiskHistoryTab } from "@/components/analytics/RiskHistoryTab";
import { SourcesTab } from "@/components/analytics/SourcesTab";
import { StudioTab } from "@/components/analytics/StudioTab";
import { TrendsTab } from "@/components/analytics/TrendsTab";
import { fetchDatasets } from "@/features/analytics/api";
import { yesterdayIso } from "@/features/analytics/format";
import { parseStudio, serializeStudio } from "@/features/analytics/studio";

const TABS = [
  { id: "chuva", label: "Chuva" },
  { id: "tendencias", label: "Tendências (1933–2025)" },
  { id: "risco", label: "Risco" },
  { id: "fontes", label: "Fontes e dados" },
  { id: "studio", label: "Studio" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function AnalyticsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const requested = params.get("aba");
  const tab: TabId = TABS.some((t) => t.id === requested) ? (requested as TabId) : "chuva";
  const datasets = useQuery({ queryKey: ["analytics", "datasets"], queryFn: ({ signal }) => fetchDatasets(signal) });
  const yesterday = yesterdayIso();
  const center = datasets.data?.find((d) => d.id === "reanalysis-daily")?.locations.find((l) => l.label === "Centro") ?? null;
  const studio = datasets.data ? parseStudio(params, datasets.data, yesterday) : null;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Análises</h1>
        <p className="text-sm text-ink-muted">
          Números calculados a partir dos dados armazenados, com fonte e tipo em cada gráfico.{" "}
          <Link className="text-accent underline" href="/analytics/datasets">
            Ver o catálogo de dados
          </Link>
          .
        </p>
        <ReportShortcut type="chuva" label="Gerar relatório de chuva" />
      </header>

      <nav aria-label="Áreas de análise" className="flex flex-wrap gap-2 border-b border-surface-border pb-2">
        {TABS.map((t) => (
          <Link
            key={t.id}
            href={`${pathname}?aba=${t.id}`}
            aria-current={tab === t.id ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === t.id ? "bg-accent text-white" : "text-accent hover:bg-surface-muted"}`}
          >
            {t.label}
          </Link>
        ))}
      </nav>

      {tab === "chuva" && (datasets.data ? <RainTab center={center} yesterday={yesterday} /> : <p className="text-sm text-ink-muted">Carregando…</p>)}
      {tab === "tendencias" && <TrendsTab />}
      {tab === "risco" && <RiskHistoryTab />}
      {tab === "fontes" && <SourcesTab />}
      {tab === "studio" &&
        (studio && datasets.data ? (
          <StudioTab
            datasets={datasets.data}
            state={studio}
            today={yesterday}
            onChange={(next) => router.replace(`${pathname}?${serializeStudio(next)}`, { scroll: false })}
          />
        ) : (
          <p className="text-sm text-ink-muted">Carregando o catálogo…</p>
        ))}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">Carregando…</p>}>
      <AnalyticsPage />
    </Suspense>
  );
}
