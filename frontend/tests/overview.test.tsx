import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { InsightList } from "@/components/overview/InsightList";
import { KpiGrid } from "@/components/overview/KpiGrid";
import { WhereSection } from "@/components/overview/WhereSection";
import { kindLabel } from "@/features/analytics/kinds";
import type { Insight, Kpi } from "@/features/analytics/types";
import type { RiskArea } from "@/features/risk/types";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

const kpis: Kpi[] = [
  {
    code: "month_to_date_rain",
    label: "Chuva do mês até ontem (centro)",
    value: 108,
    unit: "mm",
    detail: "169% da média dos mesmos 18 dias (1991–2020, reanálise)",
    period_start: "2026-11-01",
    period_end: "2026-11-18",
    kind: "MODELED",
    source: "Open-Meteo (reanálise ERA5/ERA5-Land)",
    freshness: "FRESH",
    href: "/analytics?aba=chuva",
    available: true,
  },
  {
    code: "risk_high_sectors",
    label: "Setores com risco estimado alto ou crítico",
    value: null,
    unit: "setores",
    detail: "sem execução de 24 h atrás",
    period_start: null,
    period_end: "2026-11-19T15:20:00Z",
    kind: "DERIVED",
    source: "Motor de risco v0 (experimental)",
    freshness: "UNKNOWN",
    href: "/risk",
    available: false,
  },
];

const insights: Insight[] = [
  {
    code: "IN-01",
    severity: "atencao",
    text: "Chuva prevista de 31 mm em 24 h na região Centro, acima de 95% dos dias de novembro desde 1991 (p95 = 2 mm).",
    metrics: [
      { name: "Chuva prevista em 24 h", value: 31, unit: "mm", kind: "FORECAST", source: "Open-Meteo (previsão)" },
      { name: "p95 diário de novembro (1991–2020)", value: 2, unit: "mm", kind: "MODELED", source: "Open-Meteo (reanálise ERA5/ERA5-Land)" },
    ],
    sources: ["Open-Meteo (previsão)"],
    rules_version: "0.1.0-experimental",
  },
  {
    code: "IN-05",
    severity: "info",
    text: "INMET — observações horárias: aguardando credencial de acesso.",
    metrics: [{ name: "Frescor", value: "UNAVAILABLE", unit: "", kind: "DERIVED", source: "estado das fontes" }],
    sources: ["estado das fontes"],
    rules_version: "0.1.0-experimental",
  },
];

describe("painel executivo (FR-084 a FR-086, AC-084)", () => {
  it("rótulos de tipo", () => {
    expect(["OBSERVED", "MODELED", "FORECAST", "DERIVED"].map(kindLabel)).toEqual([
      "Medido",
      "Modelo",
      "Previsão",
      "Calculado",
    ]);
  });

  it("cada KPI mostra valor, tipo, fonte e leva à análise", async () => {
    const { container } = render(<KpiGrid items={kpis} />);
    const mtd = screen.getByRole("link", { name: /Chuva do mês até ontem/ });
    expect(mtd).toHaveAttribute("href", "/analytics?aba=chuva");
    expect(within(mtd).getByText("Modelo")).toBeInTheDocument();
    expect(within(mtd).getByText("Open-Meteo (reanálise ERA5/ERA5-Land)")).toBeInTheDocument();
    expect(mtd).toHaveTextContent("108,0 mm");
    expect(mtd).toHaveTextContent("Atualizado");
    const risk = screen.getByRole("link", { name: /risco estimado alto/ });
    expect(risk).toHaveTextContent("Indisponível");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("insights mostram a frase, a severidade e os números usados", async () => {
    const { container } = render(<InsightList items={insights} notes={["nota"]} rulesVersion="0.1.0-experimental" />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Atenção: Chuva prevista de 31 mm");
    expect(items[1]).toHaveTextContent("Informação: INMET");
    expect(within(items[0]!).getByText("Números usados (IN-01)")).toBeInTheDocument();
    expect(within(items[0]!).getByText("Previsão")).toBeInTheDocument();
    expect(within(items[0]!).getByText("31 mm")).toBeInTheDocument();
    expect(screen.getByText("nota")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("sem insights explica que nenhuma regra disparou", () => {
    render(<InsightList items={[]} notes={[]} rulesVersion="v" />);
    expect(screen.getByText(/Nenhuma regra disparou agora/)).toBeInTheDocument();
  });

  it("onde: setores e ocorrências recentes", () => {
    const area = {
      id: 4,
      code: "HMP-01-03",
      name: "FAVELA DA PAZ",
      subprefecture: "SAO MIGUEL PAULISTA",
      category: "HIGH",
    } as RiskArea;
    render(
      <WhereSection
        areas={[area]}
        occurrences={{
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Point", coordinates: [-46.41, -23.47] },
              properties: { type: "ALAGAMENTO", occurred_on: "2026-09-21", subprefecture: "SAO MIGUEL PAULISTA", kind: "OBSERVED" },
            },
          ],
        }}
      />,
    );
    expect(screen.getByRole("link", { name: "HMP-01-03" })).toHaveAttribute("href", "/risk?setor=4");
    expect(screen.getByText(/Alagamento em 21\/09\/2026/)).toBeInTheDocument();
  });
});
