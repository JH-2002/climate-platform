import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { ScenarioForm } from "@/components/simulation/ScenarioForm";
import { SimulationBanner } from "@/components/simulation/SimulationBanner";
import { SimulatedSectorTable, SimulationSummary } from "@/components/simulation/SimulationResults";
import {
  DEFAULT_SCENARIO,
  parseSimulationState,
  peakHourMm,
  serializeSimulationState,
  validateScenario,
} from "@/features/simulation/scenario";
import type { Preset, SimulatedSector, SimulationRun } from "@/features/simulation/types";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

const presets: Preset[] = [
  {
    code: "chuva-persistente",
    name: "Chuva persistente",
    description: "80 mm em 12 h, constante, na cidade inteira, com 30 mm nas 72 h anteriores.",
    origin: "Faixa “forte” de 24 h do motor de risco (60 a 100 mm).",
    scenario: { total_mm: 80, duration_h: 12, pattern: "CONSTANT", antecedent_mm: 30, cell: null },
  },
];

const run: SimulationRun = {
  id: "4f9c2a8e-1b2d-4c3e-9f00-123456789abc",
  created_at: "2026-11-20T16:00:00Z",
  kind: "SIMULATED",
  mode: "SIMULATION",
  scenario: { total_mm: 60, duration_h: 1, pattern: "CONSTANT", antecedent_mm: 0, cell: null },
  scenario_text: "60 mm em 1 hora, constante, na cidade inteira; 0 mm nas 72 h anteriores",
  preset: null,
  seed: null,
  members: 1,
  simulation_engine_version: "0.1.0-experimental",
  risk_engine_version: "0.1.0-experimental",
  sectors_fingerprint: "abc",
  sectors_changed: false,
  sector_count: 6,
  counts: { CRITICAL: 3, HIGH: 2, MODERATE: 1, LOW: 0, UNKNOWN: 0 },
  comparison: {
    real_run: { id: 1, computed_at: "2026-11-20T15:51:00Z", stale: false },
    real_counts: { CRITICAL: 0, HIGH: 0, MODERATE: 0, LOW: 4, UNKNOWN: 2 },
    raised: 4,
    lowered: 0,
    unchanged: 0,
    not_comparable: 2,
    subprefectures: [
      { name: "SAO MIGUEL PAULISTA", sectors: 3, high_or_above_simulated: 3, high_or_above_real: 0, raised: 3 },
    ],
  },
  duration_ms: 42,
  banner: "SIMULAÇÃO — cenário hipotético, não é previsão nem alerta",
  disclaimer: "Cenário hipotético.",
};

const sector: SimulatedSector = {
  id: 4,
  code: "HMP-01-03",
  name: "FAVELA DA PAZ",
  subprefecture: "SAO MIGUEL PAULISTA",
  grade: 3,
  households: 85,
  category: "CRITICAL",
  real_category: "LOW",
  rain_level: 3,
  susceptibility: 4,
  p1h_max_mm: 60,
  p24_mm: 60,
  a72_mm: 0,
  rain_factor: 1,
  distance_km: null,
  factors: [{ code: "RAIN_P1H", text: "Chuva muito forte no cenário (60 mm em 1 h)", effect: "raises" }],
};

function form(overrides: Partial<Parameters<typeof ScenarioForm>[0]> = {}) {
  const props = {
    scenario: DEFAULT_SCENARIO,
    preset: null,
    presets,
    centers: [{ name: "SAO MIGUEL PAULISTA", latitude: -23.49, longitude: -46.44, sectors: 56 }],
    locations: [],
    pending: false,
    error: null,
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    ...overrides,
  };
  return { props, ...render(<ScenarioForm {...props} />) };
}

describe("SimulationBanner (BR-100, AC-107)", () => {
  it("anuncia a simulação como nota acessível", async () => {
    const { container } = render(<SimulationBanner />);
    const note = screen.getByRole("note", { name: "Aviso de simulação" });
    expect(note).toHaveTextContent("Simulação — cenário hipotético, não é previsão nem alerta");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("diferencia o modo híbrido", () => {
    render(<SimulationBanner hybrid />);
    expect(screen.getByRole("note")).toHaveTextContent("a partir da previsão real");
  });
});

describe("ScenarioForm", () => {
  it("preset preenche o cenário e mostra a origem do número (AC-102)", () => {
    const onChange = vi.fn();
    form({ onChange });
    fireEvent.click(screen.getByRole("button", { name: "Chuva persistente" }));
    expect(onChange).toHaveBeenCalledWith(presets[0]!.scenario, "chuva-persistente");
  });

  it("mostra a origem do preset escolhido", () => {
    form({ scenario: presets[0]!.scenario, preset: "chuva-persistente" });
    expect(screen.getByText(/Origem do número: Faixa “forte” de 24 h/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chuva persistente" })).toHaveAttribute("aria-pressed", "true");
  });

  it("bloqueia valores fora da faixa, com mensagem", () => {
    const onSubmit = vi.fn();
    form({ scenario: { ...DEFAULT_SCENARIO, total_mm: 400 }, onSubmit });
    expect(screen.getByText("Informe de 1 a 300 mm.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Simular" })).toBeDisabled();
  });

  it("escolhe o centro por subprefeitura, sem mapa (NFR-103)", () => {
    const onChange = vi.fn();
    form({ onChange });
    fireEvent.change(screen.getByLabelText("Centro da célula"), { target: { value: "sub:SAO MIGUEL PAULISTA" } });
    expect(onChange).toHaveBeenCalledWith(
      { ...DEFAULT_SCENARIO, cell: { latitude: -23.49, longitude: -46.44, radius_km: 6 } },
      null,
    );
  });

  it("não tem violações graves de acessibilidade", async () => {
    const { container } = form();
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("estado na URL", () => {
  it("ida e volta preserva o cenário", () => {
    const state = {
      scenario: { total_mm: 30, duration_h: 3, pattern: "PEAKED" as const, antecedent_mm: 100, cell: { latitude: -23.5, longitude: -46.6, radius_km: 8 } },
      preset: null,
      runId: run.id,
      sectorId: 4,
    };
    expect(parseSimulationState(new URLSearchParams(serializeSimulationState(state)))).toEqual(state);
  });

  it("cidade inteira e identificador inválido", () => {
    const parsed = parseSimulationState(new URLSearchParams("area=cidade&execucao=abc"));
    expect(parsed.scenario.cell).toBeNull();
    expect(parsed.runId).toBeNull();
  });

  it("hora mais forte igual ao backend", () => {
    expect(peakHourMm({ ...DEFAULT_SCENARIO, total_mm: 100, duration_h: 24, pattern: "SHARP" })).toBe(70);
    expect(peakHourMm({ ...DEFAULT_SCENARIO, total_mm: 80, duration_h: 12, pattern: "CONSTANT" })).toBeCloseTo(6.667, 2);
    expect(validateScenario({ ...DEFAULT_SCENARIO, duration_h: 1.5 })).toHaveProperty("duration");
  });
});

describe("resultado", () => {
  it("resume a simulação e compara com o real (FR-106)", () => {
    render(<SimulationSummary run={run} />);
    expect(screen.getByText(/60 mm em 1 hora/)).toBeInTheDocument();
    expect(screen.getByText(/4 setores sobem de categoria/)).toBeInTheDocument();
    const counts = screen.getByRole("list", { name: "Setores por categoria na simulação" });
    expect(within(counts).getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByRole("rowheader", { name: "Sao Miguel Paulista" })).toBeInTheDocument();
  });

  it("tabela traz a categoria simulada e a real, com rótulo de cenário hipotético", async () => {
    const onSelect = vi.fn();
    const { container } = render(<SimulatedSectorTable items={[sector]} total={1} selectedId={null} onSelect={onSelect} />);
    expect(screen.getByText(/cenário hipotético/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ver explicação do setor HMP-01-03 na simulação" }));
    expect(onSelect).toHaveBeenCalledWith(4);
    expect(await seriousViolations(container)).toEqual([]);
  });
});
