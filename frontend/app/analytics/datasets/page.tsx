"use client";

import { useQuery } from "@tanstack/react-query";
import { DatasetCard } from "@/components/analytics/DatasetCard";
import { fetchDatasets } from "@/features/analytics/api";

/** Data Explorer (FR-095): o que existe, de onde vem, de que tipo é e com que qualidade. */
export default function DatasetsPage() {
  const datasets = useQuery({ queryKey: ["analytics", "datasets"], queryFn: ({ signal }) => fetchDatasets(signal) });
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Explorador de dados</h1>
        <p className="text-sm text-ink-muted">
          Conjuntos usados pela plataforma, com fonte, licença, período, cobertura e estatísticas.
          Medido, modelo, previsão e calculado são tipos diferentes: não devem ser somados entre si.
        </p>
      </header>
      {datasets.isPending && (
        <div role="status" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
          <span className="sr-only">Carregando o catálogo…</span>
        </div>
      )}
      {datasets.isError && <p role="alert">Não foi possível carregar o catálogo. {datasets.error.message}</p>}
      {datasets.data?.map((d) => <DatasetCard key={d.id} dataset={d} />)}
    </div>
  );
}
