import Link from "next/link";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LEVEL_LABELS } from "@/features/alerts/labels";
import type { SystemAlert } from "@/features/alerts/types";
import { formatDateTime } from "@/lib/format";

function link(alert: SystemAlert): { href: string; label: string } {
  if (alert.rule_code === "risk-subprefecture") return { href: "/risk", label: "Ver os setores na página de Risco" };
  return { href: "/status", label: "Ver o estado das fontes" };
}

/** Alerta do sistema: estimativa experimental ou saúde dos dados, nunca alerta oficial. */
export function SystemAlertCard({ alert }: { alert: SystemAlert }) {
  const target = link(alert);
  const tone = alert.level === "CRITICAL" ? "error" : "warn";
  return (
    <article aria-labelledby={`sistema-${alert.id}`} className="space-y-2 rounded-lg border border-dashed border-surface-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded border border-ink-muted px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          {alert.category_label}
        </span>
        <StatusBadge tone={tone} label={LEVEL_LABELS[alert.level] ?? alert.level} />
      </div>
      <h3 id={`sistema-${alert.id}`} className="text-base font-semibold">
        {alert.title}
      </h3>
      <p className="text-sm">{alert.message}</p>
      <p className="text-xs text-ink-muted">
        Aberto em {formatDateTime(alert.opened_at)}
        {alert.updated_at !== alert.opened_at && ` · atualizado em ${formatDateTime(alert.updated_at)}`} · regra{" "}
        {alert.rule_code} (versão {alert.rules_version}) ·{" "}
        <Link href={target.href} className="font-medium text-accent underline">
          {target.label}
        </Link>
      </p>
    </article>
  );
}
