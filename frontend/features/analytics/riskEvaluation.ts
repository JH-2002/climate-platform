/** Textos da avaliação retrospectiva do motor (spec 015, FR-216, BR-210). Funções puras. */

import { formatNumber } from "@/lib/format";
import { pct, periodLabel } from "./format";
import type { ContingencyTable, RiskEvaluation } from "./types";

/** "De cada 10 dias-subprefeitura com ocorrência, o sistema marcou N" (arredondado). */
export function detectionSentence(table: ContingencyTable): string {
  if (table.pod === null || table.events === 0) {
    return "Não houve dia-subprefeitura com ocorrência registrada no período avaliado.";
  }
  const ofTen = Math.round(table.pod * 10);
  return `De cada 10 dias-subprefeitura com alagamento registrado, o sistema marcou ${ofTen} como alto ou crítico (taxa de detecção de ${pct(table.pod)}).`;
}

export function falseAlarmSentence(table: ContingencyTable): string {
  if (table.far === null) return "O sistema não marcou nenhum dia-subprefeitura como alto ou crítico no período.";
  return `Dos dias-subprefeitura marcados como alto ou crítico, ${pct(table.far)} ficaram sem ocorrência registrada — parte pode ser alagamento que não foi registrado.`;
}

function thresholds(values: number[], factor: number): string {
  return values.map((v) => formatNumber(Math.round(v * factor * 10) / 10, v * factor < 10 ? 1 : 0)).join(", ");
}

/** Recomendação da calibração (FR-214): só texto; o motor oficial não muda. */
export function calibrationSentence(data: RiskEvaluation): string {
  const best = data.best_factor;
  const current = data.calibration.find((r) => r.factor === 1);
  const winner = data.calibration.find((r) => r.factor === best);
  if (best === null || !current || !winner) return "Sem dados suficientes para comparar faixas de chuva.";
  if (best === 1) {
    return "Entre as faixas testadas, as atuais tiveram o melhor índice de sucesso crítico.";
  }
  const direction = best < 1 ? "mais baixas" : "mais altas";
  return (
    `Faixas ${direction} (fator ${formatNumber(best, 1)}: ${thresholds(data.current_thresholds.p1h_mm, best)} mm em 1 h e ` +
    `${thresholds(data.current_thresholds.p24_mm, best)} mm em 24 h) teriam o melhor índice de sucesso crítico: ` +
    `${pct(winner.csi)} contra ${pct(current.csi)}, com detecção de ${pct(current.pod)} para ${pct(winner.pod)} ` +
    `e alarmes falsos de ${pct(current.far)} para ${pct(winner.far)}. É uma recomendação: o motor oficial não muda sem nova versão.`
  );
}

export function periodSentence(data: RiskEvaluation): string {
  const { start, end, days } = data.period;
  if (!start || !end) return "Sem dias avaliados.";
  const fmt = (iso: string) => periodLabel(iso, "day");
  return `${days} dias (${fmt(start)} a ${fmt(end)}) em ${data.subprefectures} subprefeituras com setores mapeados: ${data.contingency.units} dias-subprefeitura, ${data.contingency.events} com ocorrência registrada.`;
}

export function monthLabel(month: string): string {
  return periodLabel(`${month}-01`, "month");
}
