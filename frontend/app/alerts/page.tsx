"use client";

import dynamic from "next/dynamic";
import { useWebGL } from "@/features/map/useCapabilities";
import { ReportShortcut } from "@/components/reports/ReportShortcut";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertHistory } from "@/components/alerts/AlertHistory";
import { OFFICIAL_COLORS } from "@/components/alerts/mapColors";
import { NotificationSettings } from "@/components/alerts/NotificationSettings";
import { AlertsPageView, Section } from "@/components/alerts/AlertsPageView";
import { OfficialAlertCard } from "@/components/alerts/OfficialAlertCard";
import { useActiveAlerts, useAlertsLayer, useOfficialAlert } from "@/features/alerts/hooks";

const AlertsMapView = dynamic(() => import("@/components/alerts/AlertsMapView"), {
  ssr: false,
  loading: () => (
    <div role="status" className="h-80 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">Carregando o mapa…</span>
    </div>
  ),
});

function AlertsPage() {
  const params = useSearchParams();
  const raw = Number(params.get("alerta"));
  const selectedId = Number.isInteger(raw) && raw > 0 ? raw : null;
  const active = useActiveAlerts();
  const layer = useAlertsLayer();
  const inList = active.data?.official.some((a) => a.id === selectedId) ?? false;
  const selected = useOfficialAlert(active.data && !inList ? selectedId : null);
  const webgl = useWebGL();
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedId && active.data) document.getElementById(`alerta-${selectedId}`)?.scrollIntoView({ block: "start" });
  }, [selectedId, active.data, selected.data]);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Alertas</h1>
        <p className="text-sm text-ink-muted">
          Primeiro, os alertas oficiais da Defesa Civil e os avisos do INMET, como as fontes
          publicaram. Depois, a estimativa experimental do sistema e o estado dos dados. Esta
          plataforma não emite alertas oficiais.
        </p>
        <ReportShortcut type="alertas" label="Gerar relatório dos alertas" />
      </header>

      {selected.data && (
        <Section id="selecionado" title="Alerta escolhido (já encerrado ou fora da lista atual)">
          <OfficialAlertCard alert={selected.data} highlighted />
        </Section>
      )}

      {active.isPending && (
        <div role="status" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
          <span className="sr-only">Carregando os alertas…</span>
        </div>
      )}
      {active.isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface p-4 text-sm">
          <p>Não foi possível carregar os alertas. Consulte os canais oficiais: Defesa Civil 199.</p>
          <button type="button" onClick={() => void active.refetch()} className="rounded-md border border-accent px-3 py-1.5 font-medium text-accent">
            Tentar novamente
          </button>
        </div>
      )}

      {active.data && (
        <>
          <Section id="mapa" title="Onde">
            {mapError && <p role="alert" className="text-sm">{mapError} A lista abaixo tem as mesmas informações.</p>}
            {webgl === false ? (
              <p className="text-sm">Este navegador não oferece WebGL para o mapa. A lista abaixo tem as mesmas informações.</p>
            ) : webgl ? (
              <AlertsMapView layer={layer.data} onError={setMapError} />
            ) : null}
            <p className="flex flex-wrap gap-4 text-xs text-ink-muted">
              <span>
                <span aria-hidden="true" className="mr-1 inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: OFFICIAL_COLORS.CIVIL_DEFENSE }} />
                Defesa Civil
              </span>
              <span>
                <span aria-hidden="true" className="mr-1 inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: OFFICIAL_COLORS.WEATHER_WARNING }} />
                INMET
              </span>
              <span>Contorno contínuo: vigente · tracejado: próximo</span>
            </p>
          </Section>
          <AlertsPageView active={active.data} selectedId={selectedId} />
          <NotificationSettings active={active.data} officialChannel={active.data.official_channel} />
          <p className="text-sm text-ink-muted">
            Os estados de atenção para alagamentos do CGE (Prefeitura) não têm acesso automático e não
            aparecem aqui:{" "}
            <a href={active.data.cge_url} target="_blank" rel="noopener noreferrer" className="font-medium text-accent underline">
              consulte o site do CGE
            </a>
            .
          </p>
        </>
      )}

      <AlertHistory />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">Carregando…</p>}>
      <AlertsPage />
    </Suspense>
  );
}
