import Link from "next/link";
import { StatusBadge } from "@/components/ui/StatusBadge";

/**
 * Visão geral — Fase 1. Ainda não há dados meteorológicos integrados, então a página
 * diz isso explicitamente em vez de mostrar números de exemplo (Constituição §7).
 */
export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Visão geral</h1>
        <p className="text-sm text-ink-muted">Região piloto: Município de São Paulo.</p>
      </header>

      <section
        aria-labelledby="dados-titulo"
        className="space-y-3 rounded-lg border border-surface-border bg-surface p-5"
      >
        <h2 id="dados-titulo" className="text-lg font-semibold">
          Dados meteorológicos
        </h2>
        <StatusBadge tone="unknown" label="Nenhuma fonte integrada ainda" />
        <p className="text-sm text-ink-muted">
          A ingestão de observações do INMET e da previsão da Open-Meteo chega na Fase 2. Até lá,
          esta página não exibe valores para não apresentar dados inexistentes como reais.
        </p>
      </section>

      <section
        aria-labelledby="sistema-titulo"
        className="space-y-3 rounded-lg border border-surface-border bg-surface p-5"
      >
        <h2 id="sistema-titulo" className="text-lg font-semibold">
          Infraestrutura
        </h2>
        <p className="text-sm text-ink-muted">
          Veja se API, banco geoespacial, fila e workers estão respondendo.
        </p>
        <Link
          href="/status"
          className="inline-block rounded-md bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Abrir estado do sistema
        </Link>
      </section>
    </div>
  );
}
