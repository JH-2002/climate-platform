import { screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { RiskEvaluationTab } from "@/components/analytics/RiskEvaluationTab";
import {
  calibrationSentence,
  detectionSentence,
  falseAlarmSentence,
  monthLabel,
  periodSentence,
} from "@/features/analytics/riskEvaluation";
import type { ContingencyTable, RiskEvaluation } from "@/features/analytics/types";
import { renderWithQuery } from "./query";

function table(hits: number, misses: number, falseAlarms: number, negatives: number): ContingencyTable {
  const events = hits + misses;
  const marked = hits + falseAlarms;
  const units = events + falseAlarms + negatives;
  return {
    hits,
    misses,
    false_alarms: falseAlarms,
    correct_negatives: negatives,
    units,
    events,
    pod: events ? hits / events : null,
    far: marked ? falseAlarms / marked : null,
    csi: hits + misses + falseAlarms ? hits / (hits + misses + falseAlarms) : null,
    bias: events ? marked / events : null,
    base_rate: units ? events / units : null,
  };
}

const current = table(30, 70, 60, 3840);
const evaluation: RiskEvaluation = {
  engine_version: "0.1.0-experimental",
  decision: "HIGH_OR_CRITICAL",
  period: { start: "2026-01-04", end: "2026-10-31", days: 301 },
  subprefectures: 14,
  contingency: current,
  reliability: [
    { category: "LOW", units: 3500, with_occurrence: 40, rate: 40 / 3500 },
    { category: "MODERATE", units: 410, with_occurrence: 30, rate: 30 / 410 },
    { category: "HIGH", units: 70, with_occurrence: 20, rate: 20 / 70 },
    { category: "CRITICAL", units: 20, with_occurrence: 10, rate: 0.5 },
  ],
  calibration: [0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5].map((factor) => ({
    factor,
    ...(factor === 0.7 ? table(50, 50, 90, 3810) : factor === 1 ? current : table(25, 75, 50, 3850)),
  })),
  best_factor: 0.7,
  current_thresholds: { p1h_mm: [10, 25, 50], p24_mm: [30, 60, 100] },
  monthly: [
    { month: "2026-01", ...table(5, 10, 8, 400) },
    { month: "2026-02", ...table(8, 12, 9, 380) },
  ],
  unmatched_subprefectures: ["PERUS"],
  sources: ["Previsão arquivada: Open-Meteo.com (CC BY 4.0)", "Ocorrências e setores: GeoSampa — Prefeitura de São Paulo"],
  computed_at: "2026-11-25T23:00:00Z",
};

describe("frases da avaliação (FR-216, BR-210)", () => {
  it("detecção em linguagem simples", () => {
    expect(detectionSentence(current)).toBe(
      "De cada 10 dias-subprefeitura com alagamento registrado, o sistema marcou 3 como alto ou crítico (taxa de detecção de 30%).",
    );
    expect(detectionSentence(table(0, 0, 2, 10))).toMatch(/Não houve dia-subprefeitura com ocorrência/);
  });

  it("alarmes falsos lembram o sub-registro", () => {
    expect(falseAlarmSentence(current)).toMatch(/^Dos dias-subprefeitura marcados como alto ou crítico, 67% ficaram sem/);
    expect(falseAlarmSentence(current)).toMatch(/não foi registrado/);
    expect(falseAlarmSentence(table(0, 5, 0, 10))).toMatch(/não marcou nenhum/);
  });

  it("calibração recomenda sem mudar o motor", () => {
    const text = calibrationSentence(evaluation);
    expect(text).toMatch(/^Faixas mais baixas \(fator 0,7: 7,0, 17,5, 35 mm em 1 h e 21, 42, 70 mm em 24 h\)/);
    expect(text).toMatch(/o motor oficial não muda/);
    expect(calibrationSentence({ ...evaluation, best_factor: 1 })).toMatch(/as atuais tiveram o melhor/);
  });

  it("período e mês", () => {
    expect(periodSentence(evaluation)).toBe(
      "301 dias (04/01/2026 a 31/10/2026) em 14 subprefeituras com setores mapeados: 4000 dias-subprefeitura, 100 com ocorrência registrada.",
    );
    expect(monthLabel("2026-03")).toBe("mar/2026");
  });
});

describe("aba Avaliação do risco (AC-212)", () => {
  it("mostra resumo, contingência, gráficos e limitações, sem violações graves", async () => {
    const { container } = renderWithQuery(<RiskEvaluationTab />, [[["analytics", "risk-evaluation"], evaluation]]);
    expect(screen.getByRole("heading", { name: "Resumo" })).toBeInTheDocument();
    expect(screen.getByText("30 acertos")).toBeInTheDocument();
    expect(screen.getByText("70 falhas")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Calibração das faixas de chuva" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mês a mês" })).toBeInTheDocument();
    expect(screen.getByText(/Ocorrência registrada é só parte dos alagamentos/)).toBeInTheDocument();
    expect(screen.getByText(/Perus/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { region: { enabled: false } } });
    expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
