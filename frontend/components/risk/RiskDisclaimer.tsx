/** Faixa fixa da spec 005 (FR-070): risco estimado ≠ alerta oficial (Constituição §7). */
export function RiskDisclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <aside
      role="note"
      aria-label="Aviso sobre o risco estimado"
      className={`rounded-lg border-l-4 border-status-warn bg-amber-50 text-ink ${compact ? "p-2 text-xs" : "p-3 text-sm"}`}
    >
      <p>
        <strong>Estimativa experimental do sistema — não é alerta oficial.</strong> Modelo
        heurístico e não validado, baseado em chuva prevista e em dados da Prefeitura. Em
        emergência, ligue <strong>199</strong> (Defesa Civil). Para avisos oficiais, acompanhe o
        CGE e a Defesa Civil.
      </p>
    </aside>
  );
}
