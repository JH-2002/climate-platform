"use client";

import Link from "next/link";
import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { RiskDisclaimer } from "@/components/risk/RiskDisclaimer";
import { RiskExplanation } from "@/components/risk/RiskExplanation";
import { RiskSummaryView } from "@/components/risk/RiskSummaryView";
import { RiskTable } from "@/components/risk/RiskTable";
import { CATEGORIES, CATEGORY_ORDER, isRiskCategory, titleCase } from "@/features/risk/categories";
import { useRiskArea, useRiskAreas, useRiskSummary } from "@/features/risk/hooks";
import { parseRiskFilters, serializeRiskFilters, type RiskFilters } from "@/features/risk/state";

function RiskPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const filters = parseRiskFilters(params);
  const summary = useRiskSummary();
  const areas = useRiskAreas(filters);
  const detail = useRiskArea(filters.sectorId);

  function update(next: RiskFilters) {
    const query = serializeRiskFilters(next);
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Risco de alagamento estimado</h1>
        <p className="text-sm text-ink-muted">
          Condição favorável a alagamento nas próximas 24 h em cada setor de risco hidrológico
          mapeado pela Prefeitura, combinando a chuva prevista com o grau do setor, as manchas de
          inundação e as ocorrências registradas.
        </p>
      </header>

      <RiskDisclaimer />

      {summary.isPending && (
        <div role="status" className="h-28 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
          <span className="sr-only">Carregando o resumo…</span>
        </div>
      )}
      {summary.isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface p-4 text-sm">
          <p>Não foi possível carregar a estimativa. {summary.error.message}</p>
          <button
            type="button"
            onClick={() => void summary.refetch()}
            className="rounded-md border border-accent px-3 py-1.5 font-medium text-accent hover:bg-accent hover:text-white"
          >
            Tentar novamente
          </button>
        </div>
      )}
      {summary.data && (
        <RiskSummaryView
          summary={summary.data}
          selected={filters.category}
          onSelect={(category) => update({ ...filters, category, sectorId: null })}
        />
      )}

      {detail.data && (
        <RiskExplanation detail={detail.data} onClose={() => update({ ...filters, sectorId: null })} />
      )}
      {detail.isError && (
        <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
          Setor não encontrado na estimativa atual.
        </p>
      )}

      <section aria-labelledby="setores-titulo" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="setores-titulo" className="text-lg font-semibold">
            Setores
          </h2>
          <div className="flex flex-wrap items-end gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-ink-muted">Categoria</span>
              <select
                className="rounded-md border border-surface-border bg-surface px-2 py-1.5"
                value={filters.category ?? ""}
                onChange={(e) =>
                  update({
                    ...filters,
                    category: isRiskCategory(e.target.value) ? e.target.value : null,
                    sectorId: null,
                  })
                }
              >
                <option value="">Todas</option>
                {CATEGORY_ORDER.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORIES[c].label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-ink-muted">Subprefeitura</span>
              <select
                className="rounded-md border border-surface-border bg-surface px-2 py-1.5"
                value={filters.subprefecture ?? ""}
                onChange={(e) =>
                  update({ ...filters, subprefecture: e.target.value || null, sectorId: null })
                }
              >
                <option value="">Todas</option>
                {(areas.data?.subprefectures ?? []).map((s) => (
                  <option key={s} value={s}>
                    {titleCase(s)}
                  </option>
                ))}
              </select>
            </label>
            <Link className="pb-1.5 font-medium text-accent underline" href="/map?modo=3d&camadas=risco,ocorrencias,regiao">
              Ver no mapa
            </Link>
          </div>
        </div>

        {areas.isPending && (
          <div role="status" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
            <span className="sr-only">Carregando os setores…</span>
          </div>
        )}
        {areas.isError && (
          <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
            Não foi possível carregar os setores. {areas.error.message}
          </p>
        )}
        {areas.data && (
          <RiskTable
            items={areas.data.items}
            total={areas.data.total}
            selectedId={filters.sectorId}
            onSelect={(id) => {
              update({ ...filters, sectorId: id });
              window.scrollTo({ top: 0 });
            }}
          />
        )}
        <p className="text-xs text-ink-muted">
          Fora dos setores mapeados o sistema não estima risco — ausência na lista não significa
          risco baixo. Faixas de chuva: 10, 25 e 50 mm em 1 h; 30, 60 e 100 mm em 24 h (coeficientes
          experimentais, spec 005).
        </p>
      </section>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">Carregando…</p>}>
      <RiskPage />
    </Suspense>
  );
}
