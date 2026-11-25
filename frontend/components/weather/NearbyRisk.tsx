import Link from "next/link";
import { RiskBadge } from "@/components/risk/RiskBadge";
import { RiskDisclaimer } from "@/components/risk/RiskDisclaimer";
import { titleCase } from "@/features/risk/categories";
import { riskHref } from "@/features/risk/state";
import type { NearestRiskArea } from "@/features/risk/types";
import { formatNumber } from "@/lib/format";

interface NearbyRiskProps {
  state: "loading" | "error" | "success";
  data?: NearestRiskArea;
}

/** Risco estimado do setor mais próximo do local escolhido (FR-071). */
export function NearbyRisk({ state, data }: NearbyRiskProps) {
  return (
    <section aria-labelledby="risco-local-titulo" className="space-y-3 rounded-lg border border-surface-border bg-surface p-4">
      <h2 id="risco-local-titulo" className="font-semibold">
        Risco de alagamento estimado aqui
      </h2>
      {state === "loading" && <p className="text-sm text-ink-muted">Carregando…</p>}
      {state === "error" && (
        <p className="text-sm text-ink-muted">Não foi possível consultar o risco estimado agora.</p>
      )}
      {state === "success" && data && !data.area && (
        <p className="text-sm text-ink-muted">
          Nenhum setor de risco hidrológico mapeado pela Prefeitura a até{" "}
          {formatNumber(data.max_distance_km, 0)} km deste local. Isso não significa que não possa
          alagar.
        </p>
      )}
      {state === "success" && data?.area && (
        <div className="space-y-2 text-sm">
          <p className="flex flex-wrap items-center gap-2">
            <RiskBadge category={data.area.category} />
            <span>
              Setor {data.area.code} ({titleCase(data.area.name)}), a{" "}
              {formatNumber(data.distance_m, 0)} m
            </span>
          </p>
          {data.area.factors[0] && <p className="text-ink-muted">{data.area.factors[0].text}.</p>}
          <Link className="font-medium text-accent underline" href={riskHref(data.area.id)}>
            Ver por que esta estimativa
          </Link>
        </div>
      )}
      <RiskDisclaimer compact />
    </section>
  );
}
