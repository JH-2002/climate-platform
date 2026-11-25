/**
 * Faixa de simulação (BR-100): em todas as telas de resultado, com cor própria (roxo com
 * listras) que não se confunde com as categorias de risco, e lida por leitores de tela.
 */
export function SimulationBanner({ hybrid = false }: { hybrid?: boolean }) {
  return (
    <aside
      role="note"
      aria-label="Aviso de simulação"
      className="rounded-lg border-2 border-violet-700 p-3 text-sm text-violet-950"
      style={{
        backgroundImage:
          "repeating-linear-gradient(135deg, #ede9fe 0 14px, #f5f3ff 14px 28px)",
      }}
    >
      <p className="font-bold uppercase tracking-wide">
        {hybrid
          ? "Simulação a partir da previsão real — cenário hipotético, não é previsão nem alerta"
          : "Simulação — cenário hipotético, não é previsão nem alerta"}
      </p>
      <p className="mt-1">
        Resultado do motor de risco v0 (experimental, não calibrado e sem hidrologia) para a chuva
        que você escolheu. Em emergência, ligue <strong>199</strong> (Defesa Civil).
      </p>
    </aside>
  );
}
