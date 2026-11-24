import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { MapLegend } from "@/components/map/MapLegend";
import { RiskBadge } from "@/components/risk/RiskBadge";
import { RiskDisclaimer } from "@/components/risk/RiskDisclaimer";
import { RiskExplanation } from "@/components/risk/RiskExplanation";
import { terrainFixture } from "./geoFixtures";
import { renderWithQuery } from "./query";
import { RiskSummaryView } from "@/components/risk/RiskSummaryView";
import { RiskTable } from "@/components/risk/RiskTable";
import { NearbyRisk } from "@/components/weather/NearbyRisk";
import { riskAreasQuery } from "@/features/risk/api";
import { CATEGORIES, CATEGORY_ORDER, RAIN_LEVEL_LABELS, titleCase } from "@/features/risk/categories";
import { parseRiskFilters, riskHref, serializeRiskFilters } from "@/features/risk/state";
import type { RiskArea, RiskAreaDetail, RiskSummary } from "@/features/risk/types";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

const area: RiskArea = {
  id: 4,
  code: "HMP-01-03",
  name: "FAVELA DA PAZ",
  subprefecture: "SAO MIGUEL PAULISTA",
  basin: "RIBEIRAO AGUA VERMELHA",
  grade: 3,
  households: 85,
  category: "HIGH",
  rain_level: 2,
  susceptibility: 4,
  p1h_max_mm: 30,
  p24_mm: 31.2,
  a72_mm: null,
  in_flood_extent_100y: true,
  nearby_occurrences_12m: 11,
  factors: [
    { code: "RAIN_P1H", text: "Chuva forte prevista (30 mm em 1 h)", effect: "raises" },
    { code: "ANTECEDENT_NA", text: "Chuva das 72 h anteriores indisponível", effect: "info" },
    { code: "GRADE", text: "Setor R3 vistoriado pela Prefeitura", effect: "raises" },
  ],
  unknown_reason: null,
};

const run = {
  id: 7,
  engine_version: "0.1.0-experimental",
  computed_at: "2026-11-19T15:20:00Z",
  valid_until: "2026-11-20T15:20:00Z",
  forecast_issued_at: "2026-11-19T15:05:00Z",
  forecast_freshness: "FRESH",
  stale: false,
};

const summary: RiskSummary = {
  run,
  counts: { LOW: 1, MODERATE: 1, HIGH: 2, CRITICAL: 0, UNKNOWN: 2 },
  sectors_freshness: "FRESH",
  disclaimer: "Estimativa experimental do sistema, heurística e não validada. Não é alerta oficial.",
  attribution: "Setores: GeoSampa — Prefeitura de São Paulo · Previsão: Open-Meteo.com (CC BY 4.0)",
  experimental: true,
};

const detail: RiskAreaDetail = {
  ...area,
  processes: ["ENCHENTE", "INUNDACAO"],
  inspected_on: "2024-05-08",
  latitude: -23.4746,
  longitude: -46.419,
  forecast_point_key: "-23.5149,-46.6105",
  forecast_distance_km: 19.6,
  inputs: [
    { name: "Chuva prevista em 24 h", value: 31.2, unit: "mm", kind: "FORECAST", source: "Open-Meteo.com (CC BY 4.0)" },
    { name: "Chuva estimada nas 72 h anteriores", value: null, unit: "mm", kind: "MODELED", source: "Open-Meteo.com (CC BY 4.0)" },
    { name: "Grau do setor (R1–R4)", value: 3, unit: "grau", kind: "OBSERVED", source: "GeoSampa — vistoria da Prefeitura" },
  ],
  nearby_occurrences: [{ type: "ALAGAMENTO", occurred_on: "2026-09-21", subprefecture: "SAO MIGUEL PAULISTA", distance_m: 25.4 }],
  run,
  official_url: "https://geosampa.prefeitura.sp.gov.br",
  disclaimer: summary.disclaimer,
};

describe("filtros da página de risco na URL", () => {
  it("lê e escreve categoria, subprefeitura e setor, ignorando valores inválidos", () => {
    const filters = parseRiskFilters(new URLSearchParams("categoria=HIGH&subprefeitura=SAO MIGUEL PAULISTA&setor=4"));
    expect(filters).toEqual({ category: "HIGH", subprefecture: "SAO MIGUEL PAULISTA", sectorId: 4 });
    expect(serializeRiskFilters(filters)).toBe("categoria=HIGH&subprefeitura=SAO+MIGUEL+PAULISTA&setor=4");
    expect(parseRiskFilters(new URLSearchParams("categoria=ALERTA&setor=-1"))).toEqual({
      category: null,
      subprefecture: null,
      sectorId: null,
    });
    expect(riskHref(12)).toBe("/risk?setor=12");
    expect(riskAreasQuery({ category: "LOW", subprefecture: null, sectorId: 3 })).toBe(
      "/api/v1/risk/areas?limit=1000&category=LOW",
    );
  });
});

describe("categorias (BR-062, BR-065, Constituição §11)", () => {
  it("cada categoria tem rótulo, cor e forma próprios", () => {
    const labels = CATEGORY_ORDER.map((c) => CATEGORIES[c].label);
    const shapes = CATEGORY_ORDER.map((c) => CATEGORIES[c].shape);
    const colors = CATEGORY_ORDER.map((c) => CATEGORIES[c].color);
    expect(labels).toEqual(["Crítico", "Alto", "Moderado", "Baixo", "Desconhecido"]);
    expect(new Set(shapes).size).toBe(5);
    expect(new Set(colors).size).toBe(5);
  });

  it("AC-067: nenhum rótulo de risco estimado usa a palavra alerta", () => {
    const texts = [
      ...CATEGORY_ORDER.map((c) => CATEGORIES[c].label),
      ...Object.values(RAIN_LEVEL_LABELS),
    ];
    for (const text of texts) expect(text.toLowerCase()).not.toContain("alerta");
    render(<RiskTable items={[area]} total={1} selectedId={null} onSelect={() => {}} />);
    const badge = screen.getByText("Alto");
    expect(badge.textContent?.toLowerCase()).not.toContain("alerta");
  });

  it("capitaliza nomes da fonte", () => {
    expect(titleCase("SAO MIGUEL PAULISTA")).toBe("Sao Miguel Paulista");
    expect(titleCase("JARDIM DA PAZ")).toBe("Jardim da Paz");
    expect(titleCase(null)).toBe("—");
    expect(titleCase("ARICANDUVA-FORMOSA-CARRAO")).toBe("Aricanduva-Formosa-Carrao");
    expect(titleCase("VILA MARIA/VILA GUILHERME")).toBe("Vila Maria/Vila Guilherme");
  });
});

describe("componentes de risco", () => {
  it("selo mostra texto e ícone decorativo", () => {
    const { container } = render(<RiskBadge category="CRITICAL" />);
    expect(screen.getByText("Crítico")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("AC-064: aviso deixa claro que não é alerta oficial e cita o 199", () => {
    render(<RiskDisclaimer />);
    const note = screen.getByRole("note", { name: "Aviso sobre o risco estimado" });
    expect(note).toHaveTextContent("não é alerta oficial");
    expect(note).toHaveTextContent("199");
  });

  it("resumo conta por categoria, filtra ao clicar e mostra versão e coleta", async () => {
    const onSelect = vi.fn();
    const { container } = render(<RiskSummaryView summary={summary} selected={null} onSelect={onSelect} />);
    const high = screen.getByRole("button", { name: /Alto\s*2\s*setores/ });
    fireEvent.click(high);
    expect(onSelect).toHaveBeenCalledWith("HIGH");
    expect(screen.getByText("0.1.0-experimental")).toBeInTheDocument();
    expect(screen.queryByText("Estimativa desatualizada")).not.toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("resumo avisa quando a estimativa está velha e quando ainda não existe", () => {
    const { rerender } = render(
      <RiskSummaryView summary={{ ...summary, run: { ...run, stale: true } }} selected={null} onSelect={() => {}} />,
    );
    expect(screen.getByText("Estimativa desatualizada")).toBeInTheDocument();
    rerender(<RiskSummaryView summary={{ ...summary, run: null }} selected={null} onSelect={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Ainda não há estimativa");
  });

  it("tabela lista o setor e abre a explicação", async () => {
    const onSelect = vi.fn();
    const { container } = render(<RiskTable items={[area]} total={6} selectedId={null} onSelect={onSelect} />);
    const row = screen.getByRole("row", { name: /HMP-01-03/ });
    expect(within(row).getByText("Sao Miguel Paulista")).toBeInTheDocument();
    expect(within(row).getByText("Chuva forte")).toBeInTheDocument();
    expect(screen.getByText(/1 de 6/)).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: "Ver explicação do setor HMP-01-03" }));
    expect(onSelect).toHaveBeenCalledWith(4);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("AC-065: explicação mostra fatores, tipo de cada dado e fontes", async () => {
    const { container } = renderWithQuery(<RiskExplanation detail={detail} onClose={() => {}} />, [
      [["geo", "sector", detail.id], terrainFixture(detail.id)],
    ]);
    expect(screen.getByRole("heading", { name: "Setor HMP-01-03 — Favela da Paz" })).toBeInTheDocument();
    expect(screen.getByText("Chuva forte prevista (30 mm em 1 h)")).toBeInTheDocument();
    expect(screen.getByText("Previsão (modelo)")).toBeInTheDocument();
    expect(screen.getByText("Estimativa de modelo")).toBeInTheDocument();
    expect(screen.getByText("indisponível")).toBeInTheDocument();
    expect(screen.getByText("R3")).toBeInTheDocument();
    expect(screen.getByText(/Alagamento em 21\/09\/2026/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir o GeoSampa (fonte oficial)" })).toHaveAttribute(
      "href",
      "https://geosampa.prefeitura.sp.gov.br",
    );
    expect(screen.getByRole("link", { name: "Ver previsão neste setor" })).toHaveAttribute(
      "href",
      expect.stringContaining("/weather?lat=-23.4746&lon=-46.4190"),
    );
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("FR-071: painel do clima mostra o setor próximo ou explica a ausência", () => {
    const { rerender } = render(
      <NearbyRisk state="success" data={{ area, distance_m: 42, max_distance_km: 2, disclaimer: "" }} />,
    );
    expect(screen.getByText("Alto")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver por que esta estimativa" })).toHaveAttribute("href", "/risk?setor=4");
    expect(screen.getByRole("note")).toHaveTextContent("199");
    rerender(<NearbyRisk state="success" data={{ area: null, distance_m: null, max_distance_km: 2, disclaimer: "" }} />);
    expect(screen.getByText(/Isso não significa que não possa alagar/)).toBeInTheDocument();
  });

  it("legenda do mapa inclui as categorias de risco com texto", () => {
    render(<MapLegend mode="3d" />);
    for (const c of CATEGORY_ORDER) expect(screen.getByText(CATEGORIES[c].label)).toBeInTheDocument();
    expect(screen.getByText("Ocorrência registrada (12 meses)")).toBeInTheDocument();
  });
});
