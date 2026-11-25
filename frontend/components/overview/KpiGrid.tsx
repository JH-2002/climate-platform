import Link from "next/link";
import { kindLabel } from "@/features/analytics/kinds";
import type { Kpi } from "@/features/analytics/types";
import { FRESHNESS_LABELS } from "@/features/sources/types";
import { formatNumber } from "@/lib/format";

function freshness(value: string | null): string | null {
  if (!value) return null;
  return (FRESHNESS_LABELS as Record<string, string>)[value] ?? value;
}

function digits(kpi: Kpi): number {
  return kpi.unit === "mm" || kpi.unit === "%" ? 1 : 0;
}

/** Indicadores com valor, tipo, fonte e frescor; cada um leva à análise (FR-084, AC-084). */
export function KpiGrid({ items }: { items: Kpi[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((kpi) => {
        const state = freshness(kpi.freshness);
        return (
          <li key={kpi.code}>
            <Link
              href={kpi.href}
              className="flex h-full flex-col gap-1 rounded-lg border border-surface-border bg-surface p-4 hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              <span className="text-sm text-ink-muted">{kpi.label}</span>
              {kpi.available && kpi.value !== null ? (
                <span className="text-2xl font-semibold tabular-nums">
                  {formatNumber(kpi.value, digits(kpi))}{" "}
                  <span className="text-sm font-normal text-ink-muted">{kpi.unit}</span>
                </span>
              ) : (
                <span className="text-lg font-semibold text-ink-muted">Indisponível</span>
              )}
              {kpi.detail && <span className="text-xs text-ink-muted">{kpi.detail}</span>}
              <span className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 pt-2 text-xs text-ink-muted">
                <span className="rounded border border-surface-border px-1.5 py-0.5 font-medium text-ink">
                  {kindLabel(kpi.kind)}
                </span>
                <span>{kpi.source}</span>
                {state && <span>· {state}</span>}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
