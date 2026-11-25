"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useActiveAlerts } from "@/features/alerts/hooks";
import { alertHref, bannerAlert, severityIcon } from "@/features/alerts/labels";
import type { ActiveAlerts } from "@/features/alerts/types";

/**
 * Faixa no topo de todas as páginas quando há alerta oficial vigente (FR-147). O leitor de
 * tela anuncia só quando aparece um alerta novo, não a cada consulta (NFR-144).
 */
export function AlertBannerView({ active }: { active: ActiveAlerts | undefined }) {
  const alert = bannerAlert(active);
  const announced = useRef<number | null>(null);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    if (!alert || announced.current === alert.id) return;
    announced.current = alert.id;
    setAnnouncement(`${alert.category_label}: ${alert.headline ?? alert.event ?? "alerta vigente"}`);
  }, [alert]);

  const others = (active?.counts.official_active ?? 0) - (alert ? 1 : 0);
  return (
    <>
      <div role="alert" className="sr-only">
        {announcement}
      </div>
      {alert && (
        <div className="border-b-4 border-status-error bg-status-error/10 px-4 py-3 md:px-8">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span aria-hidden="true" className="text-lg text-status-error">
              {severityIcon(alert.severity)}
            </span>
            <span className="font-semibold">{alert.category_label}</span>
            <span className="text-ink-muted">· {alert.level_name ?? `severidade ${alert.severity_label.toLowerCase()}`}</span>
            <span className="min-w-0 flex-1 basis-64">{alert.headline ?? alert.event}</span>
            <Link href={alertHref(alert.id)} className="font-medium text-accent underline">
              Ver alerta{others > 0 ? ` e mais ${others}` : ""}
            </Link>
          </div>
        </div>
      )}
    </>
  );
}

export function AlertBanner() {
  const { data } = useActiveAlerts();
  return <AlertBannerView active={data} />;
}
