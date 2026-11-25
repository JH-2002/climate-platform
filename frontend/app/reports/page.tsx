"use client";

import { useQuery } from "@tanstack/react-query";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ReportForm } from "@/components/reports/ReportForm";
import { ReportList } from "@/components/reports/ReportList";
import { fetchDatasets } from "@/features/analytics/api";
import { apiParams, defaultForm, formFromUrl } from "@/features/reports/form";
import { useCreateReport, useReportIds, useReports, useReportTypes } from "@/features/reports/hooks";
import type { ReportForm as Form } from "@/features/reports/types";
import { fetchRiskAreas } from "@/features/risk/api";

function ReportsPage() {
  const params = useSearchParams();
  const types = useReportTypes();
  const { ids, add } = useReportIds();
  const reports = useReports(ids);
  const [form, setForm] = useState<Form>(() => defaultForm(new Date()));
  const [error, setError] = useState<string | null>(null);
  const create = useCreateReport((request) => add(request.id));

  // Atalhos de outras páginas preenchem o formulário pela URL.
  useEffect(() => setForm(formFromUrl(params, new Date())), [params]);

  const subprefectures = useQuery({
    queryKey: ["reports", "subprefectures"],
    queryFn: async ({ signal }) =>
      (await fetchRiskAreas({ category: null, subprefecture: null, sectorId: null }, signal)).subprefectures,
    enabled: form.type === "risco",
    staleTime: 60 * 60_000,
  });
  const points = useQuery({
    queryKey: ["analytics", "datasets"],
    queryFn: ({ signal }) => fetchDatasets(signal),
    enabled: form.type === "chuva",
    select: (datasets) =>
      (datasets.find((d) => d.id === "reanalysis-daily")?.locations ?? []).map((l) => ({
        key: l.key,
        label: `${l.label} (${l.key})`,
      })),
  });

  function submit() {
    setError(null);
    create.mutate(
      { type: form.type, format: form.format, params: apiParams(form) },
      { onError: (e) => setError(e.message) },
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Relatórios</h1>
        <p className="text-sm text-ink-muted">
          PDF, CSV ou JSON com os mesmos números das telas, sempre com a fonte, o tipo do dado
          (medido, previsão, modelo, calculado ou simulado), o horário e os avisos.
        </p>
      </header>

      {types.isPending && (
        <div role="status" className="h-40 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
          <span className="sr-only">Carregando os tipos de relatório…</span>
        </div>
      )}
      {types.isError && (
        <p role="alert" className="rounded-lg border border-surface-border bg-surface p-4 text-sm">
          Não foi possível carregar os tipos de relatório. {types.error.message}
        </p>
      )}
      {types.data && (
        <ReportForm
          types={types.data}
          form={form}
          subprefectures={subprefectures.data ?? []}
          points={points.data ?? []}
          pending={create.isPending}
          error={error}
          onChange={setForm}
          onSubmit={submit}
        />
      )}

      <section aria-labelledby="meus-relatorios" className="space-y-3">
        <h2 id="meus-relatorios" className="text-lg font-semibold">
          Pedidos deste navegador
        </h2>
        {reports.isError ? (
          <p role="alert" className="text-sm">
            Não foi possível consultar os pedidos. {reports.error.message}
          </p>
        ) : (
          <ReportList items={reports.data ?? []} />
        )}
        <p className="text-xs text-ink-muted">
          A lista fica só neste navegador. Os arquivos são apagados 7 dias depois de gerados.
        </p>
      </section>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">Carregando…</p>}>
      <ReportsPage />
    </Suspense>
  );
}
