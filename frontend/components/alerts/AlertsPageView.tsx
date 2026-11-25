"use client";

import type { ReactNode } from "react";
import { AlertSourceStatus } from "@/components/alerts/AlertSourceStatus";
import { OfficialAlertCard } from "@/components/alerts/OfficialAlertCard";
import { SystemAlertCard } from "@/components/alerts/SystemAlertCard";
import { CATEGORY_TITLES, officialByCategory, systemByCategory } from "@/features/alerts/labels";
import type { ActiveAlerts, OfficialAlert, SystemAlert } from "@/features/alerts/types";

export function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-4 space-y-3">
      <h2 id={`${id}-titulo`} className="text-lg font-semibold">
        {title}
      </h2>
      {intro && <p className="text-sm text-ink-muted">{intro}</p>}
      {children}
    </section>
  );
}

function OfficialList({
  alerts,
  empty,
  selectedId,
}: {
  alerts: OfficialAlert[];
  empty: string;
  selectedId: number | null;
}) {
  if (alerts.length === 0) return <p className="rounded-lg border border-surface-border bg-surface p-4 text-sm">{empty}</p>;
  return (
    <div className="space-y-3">
      {alerts.map((a) => (
        <OfficialAlertCard key={a.id} alert={a} highlighted={a.id === selectedId} />
      ))}
    </div>
  );
}

function SystemList({ alerts, empty }: { alerts: SystemAlert[]; empty: string }) {
  if (alerts.length === 0) return <p className="rounded-lg border border-surface-border bg-surface p-4 text-sm">{empty}</p>;
  return (
    <div className="space-y-3">
      {alerts.map((a) => (
        <SystemAlertCard key={a.id} alert={a} />
      ))}
    </div>
  );
}

function emptyOfficial(active: ActiveAlerts, source: string, what: string): string {
  const ok = active.sources.find((s) => s.code === source);
  if (!ok || ok.freshness === "STALE" || ok.freshness === "UNAVAILABLE" || ok.freshness === "UNKNOWN") {
    return `A fonte está atrasada ou indisponível: não dá para afirmar que não há ${what} agora.`;
  }
  return `Nenhum ${what} vigente ou previsto para a cidade agora.`;
}

/** Página de alertas (spec 009, FR-146): oficiais primeiro, depois a estimativa e os dados. */
export function AlertsPageView({ active, selectedId }: { active: ActiveAlerts; selectedId: number | null }) {
  const civil = officialByCategory(active, "CIVIL_DEFENSE");
  const inmet = officialByCategory(active, "WEATHER_WARNING");
  return (
    <>
      <Section id="defesa-civil" title={CATEGORY_TITLES.CIVIL_DEFENSE} intro="Mensagens que a Defesa Civil enviou à população, com o texto e a área como a fonte publicou.">
        <OfficialList alerts={civil} empty={emptyOfficial(active, "idap-alerts", "alerta da Defesa Civil")} selectedId={selectedId} />
      </Section>
      <Section id="inmet" title={CATEGORY_TITLES.WEATHER_WARNING} intro="Avisos do INMET para a região metropolitana, com até 5 dias de antecedência. A área é a da mesorregião, não de bairros.">
        <OfficialList alerts={inmet} empty={emptyOfficial(active, "inmet-warnings", "aviso do INMET")} selectedId={selectedId} />
      </Section>
      <AlertSourceStatus sources={active.sources} ok={active.sources_ok} />
      <Section
        id="estimativa"
        title={CATEGORY_TITLES.RISK_ESTIMATE}
        intro="Subprefeituras com setor em risco alto ou crítico na estimativa experimental do motor v0. Não substitui os alertas acima."
      >
        <SystemList alerts={systemByCategory(active, "RISK_ESTIMATE")} empty="Nenhuma subprefeitura em risco alto ou crítico na estimativa mais recente." />
      </Section>
      <Section id="dados" title={CATEGORY_TITLES.DATA_QUALITY}>
        <SystemList alerts={systemByCategory(active, "DATA_QUALITY")} empty="Fontes essenciais em dia." />
      </Section>
    </>
  );
}
