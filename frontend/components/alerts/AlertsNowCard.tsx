"use client";

import Link from "next/link";
import { useActiveAlerts } from "@/features/alerts/hooks";
import { alertHref, severityIcon } from "@/features/alerts/labels";
import type { ActiveAlerts } from "@/features/alerts/types";

/** Cartão "Alertas agora" (FR-148): oficiais primeiro; "nenhum" só com as fontes em dia. */
export function AlertsNowCardView({ active }: { active: ActiveAlerts }) {
  const official = active.official.slice(0, 3);
  const risk = active.counts.risk_estimate ?? 0;
  return (
    <div className="space-y-3 rounded-lg border border-surface-border bg-surface p-4 text-sm">
      {official.length > 0 ? (
        <ul className="space-y-2">
          {official.map((a) => (
            <li key={a.id} className="flex gap-2">
              <span aria-hidden="true">{severityIcon(a.severity)}</span>
              <span>
                <span className="font-medium">{a.category_label}</span>
                {a.status === "UPCOMING" ? " (próximo)" : ""}: {a.headline ?? a.event}{" "}
                <Link href={alertHref(a.id)} className="text-accent underline">
                  detalhes
                </Link>
              </span>
            </li>
          ))}
        </ul>
      ) : active.sources_ok ? (
        <p>Nenhum alerta oficial da Defesa Civil ou do INMET para a cidade agora.</p>
      ) : (
        <p className="font-medium text-status-warn">
          Fontes de alerta atrasadas: não dá para afirmar que não há alerta oficial agora.
        </p>
      )}
      {active.official.length > official.length && (
        <p className="text-ink-muted">E mais {active.official.length - official.length} alerta(s) oficial(is).</p>
      )}
      <p className="text-ink-muted">
        {risk > 0
          ? `Estimativa do sistema (não é alerta oficial): risco alto ou crítico em ${risk} subprefeitura(s).`
          : "Estimativa do sistema: nenhuma subprefeitura em risco alto ou crítico."}
      </p>
      <Link href="/alerts" className="font-medium text-accent underline">
        Ver todos os alertas
      </Link>
    </div>
  );
}

export function AlertsNowCard() {
  const query = useActiveAlerts();
  if (query.isPending)
    return (
      <div role="status" className="h-24 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
        <span className="sr-only">Carregando os alertas…</span>
      </div>
    );
  if (query.isError)
    return (
      <p role="alert" className="rounded-lg border border-surface-border bg-surface p-4 text-sm">
        Não foi possível carregar os alertas. Consulte também os canais oficiais (Defesa Civil: 199).
      </p>
    );
  return <AlertsNowCardView active={query.data} />;
}
