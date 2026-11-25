import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { ScenarioForm } from "@/components/simulation/ScenarioForm";
import { SimulationBanner } from "@/components/simulation/SimulationBanner";
import { RecentRuns, SimulatedSectorTable, SimulationSummary } from "@/components/simulation/SimulationResults";
import {
  DEFAULT_OPTIONS,
  DEFAULT_SCENARIO,
  fromRun,
  requestBody,
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
  scenario: {
    total_mm: 60,
    duration_h: 1,
    pattern: "CONSTANT",
    antecedent_mm: 0,
    cell: null,
    hybrid: null,
    uncertainty: null,
  },
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
  forecast_issued_at: null,
  ensemble: null,
  repeat_of: null,
  repeat_check: null,
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
  p_high: null,
  p_critical: null,
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
      options: { ...DEFAULT_OPTIONS },
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
    fireEvent.click(screen.getByRole("button", { name: "Por quê? Explicação do setor HMP-01-03 na simulação" }));
    expect(onSelect).toHaveBeenCalledWith(4);
    expect(await seriousViolations(container)).toEqual([]);
  });
});

const hybridRun: SimulationRun = {
  ...run,
  mode: "HYBRID",
  seed: 42,
  members: 50,
  scenario: {
    ...run.scenario,
    hybrid: { multiplier: 2, add_storm: false },
    uncertainty: { members: 50, intensity_pct: 20, shift_km: 0 },
  },
  scenario_text: "previsão real × 200%; chuva das 72 h anteriores real; 50 variações",
  forecast_issued_at: "2026-11-20T15:05:00Z",
  ensemble: { members: 50, mean: 12.4, p10: 8, p90: 17, minimum: 5, maximum: 21 },
  repeat_of: "11111111-2222-4333-8444-555555555555",
  repeat_check: {
    original_id: "11111111-2222-4333-8444-555555555555",
    same_engine_versions: true,
    same_sectors: true,
    same_forecast: false,
    identical_results: false,
  },
  banner: "SIMULAÇÃO A PARTIR DA PREVISÃO REAL — cenário hipotético, não é previsão nem alerta",
};

describe("Parte B: modo híbrido, variações e histórico", () => {
  it("estado da URL guarda modo, multiplicador e seed", () => {
    const state = {
      scenario: DEFAULT_SCENARIO,
      options: { mode: "HYBRID" as const, multiplier: 2, add_storm: true, members: 30, intensity_pct: 25, shift_km: 4, seed: 7 },
      preset: null,
      runId: null,
      sectorId: null,
    };
    const query = serializeSimulationState(state);
    expect(query).toContain("modo=hibrido");
    expect(query).toContain("mult=200");
    expect(parseSimulationState(new URLSearchParams(query))).toEqual(state);
  });

  it("valida multiplicador e variações; no híbrido sem chuva extra ignora o cenário", () => {
    const hybrid = { ...DEFAULT_OPTIONS, mode: "HYBRID" as const, multiplier: 4 };
    expect(validateScenario({ ...DEFAULT_SCENARIO, total_mm: 0 }, hybrid)).toEqual({ multiplier: "Informe de 50% a 300%." });
    expect(validateScenario(DEFAULT_SCENARIO, { ...DEFAULT_OPTIONS, members: 120 })).toHaveProperty("members");
  });

  it("corpo da requisição: sem variações não manda seed nem deslocamento", () => {
    const body = requestBody(DEFAULT_SCENARIO, { ...DEFAULT_OPTIONS, seed: 9 }, "pancada-de-verao");
    expect(body).toMatchObject({ mode: "SIMULATION", members: 1, seed: null, shift_km: 0, preset: "pancada-de-verao" });
    const repeat = requestBody(fromRun(hybridRun).scenario, fromRun(hybridRun).options, null, hybridRun.id);
    expect(repeat).toMatchObject({ mode: "HYBRID", multiplier: 2, members: 50, seed: 42, repeat_of: hybridRun.id });
  });

  it("formulário troca para o modo a partir da previsão real", () => {
    const onOptionsChange = vi.fn();
    form({ onOptionsChange });
    fireEvent.click(screen.getByLabelText("A partir da previsão real das próximas 24 h"));
    expect(onOptionsChange).toHaveBeenCalledWith({ ...DEFAULT_OPTIONS, mode: "HYBRID" });
  });

  it("no híbrido sem chuva extra o formulário esconde o cenário e mostra o multiplicador", async () => {
    const { container } = form({ options: { ...DEFAULT_OPTIONS, mode: "HYBRID" }, onOptionsChange: vi.fn() });
    expect(screen.getByLabelText("Chuva prevista multiplicada por (%)")).toHaveValue(100);
    expect(screen.queryByLabelText("Chuva total (mm)")).toBeNull();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("mostra seed e campos de incerteza com variações", () => {
    form({ options: { ...DEFAULT_OPTIONS, members: 20 }, onOptionsChange: vi.fn() });
    expect(screen.getByLabelText("Seed")).toHaveAttribute("placeholder", "sorteado");
    expect(screen.getByLabelText("Centro se desloca até (km)")).toBeInTheDocument();
  });

  it("resumo do híbrido: previsão usada, faixa de variações e aviso de repetição diferente", () => {
    const onRepeat = vi.fn();
    render(<SimulationSummary run={hybridRun} onRepeat={onRepeat} />);
    expect(screen.getByText(/Partiu da previsão real emitida em/)).toBeInTheDocument();
    expect(screen.getByText(/em 80% das variações, entre 8 e 17/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("resultado diferente porque a previsão real foi atualizada");
    fireEvent.click(screen.getByRole("button", { name: "Repetir (seed 42)" }));
    expect(onRepeat).toHaveBeenCalled();
  });

  it("tabela mostra a chance de alto ou crítico quando há variações", () => {
    render(
      <SimulatedSectorTable
        items={[{ ...sector, p_high: 0.84, p_critical: 0.3 }]}
        total={1}
        selectedId={null}
        onSelect={vi.fn()}
        withProbability
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Chance de alto ou crítico" })).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument();
    expect(screen.getByText("crítico: 30%")).toBeInTheDocument();
  });

  it("histórico lista as simulações recentes com link", () => {
    render(
      <RecentRuns
        currentId={run.id}
        items={[
          { id: run.id, created_at: run.created_at, mode: "SIMULATION", scenario_text: "60 mm em 1 hora", preset: null, seed: null, members: 1, high_or_above: 5, unknown: 0 },
          { id: "11111111-2222-4333-8444-555555555555", created_at: run.created_at, mode: "HYBRID", scenario_text: "previsão real × 200%", preset: null, seed: 42, members: 50, high_or_above: 12, unknown: 2 },
        ]}
      />,
    );
    expect(screen.getByRole("link", { name: "60 mm em 1 hora" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText(/a partir da previsão real · 12 setores em alto ou crítico · 2 desconhecidos · seed 42/)).toBeInTheDocument();
  });
});
