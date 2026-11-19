"use client";

import { ReadinessView } from "@/components/system/ReadinessView";
import { useReadiness } from "@/features/system/useReadiness";
import { ApiError } from "@/lib/api-client";

export default function StatusPage() {
  const readiness = useReadiness();
  const error = readiness.error;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Estado do sistema</h1>
        <p className="text-sm text-ink-muted">
          Verificação em tempo real da API, do banco geoespacial, da fila e dos workers. Cada
          consulta testa os componentes de novo, sem cache.
        </p>
      </header>
      <ReadinessView
        state={readiness.viewState}
        report={readiness.data}
        errorMessage={error?.message}
        correlationId={error instanceof ApiError ? error.correlationId : null}
        isRefreshing={readiness.isFetching}
        onRetry={() => void readiness.refetch()}
      />
    </div>
  );
}
