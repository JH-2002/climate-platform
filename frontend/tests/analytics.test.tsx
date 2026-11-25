import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { ChartFrame } from "@/components/analytics/ChartFrame";
import { seriesCsvUrl, seriesQuery } from "@/features/analytics/api";
import { mm, periodLabel, pct } from "@/features/analytics/format";
import {
  compatibleComparisons,
  compatibleVisualizations,
  defaultState,
  equalBins,
  parseStudio,
  serializeStudio,
} from "@/features/analytics/studio";
import type { DatasetInfo } from "@/features/analytics/types";

function dataset(overrides: Partial<DatasetInfo>): DatasetInfo {
  return {
    id: "reanalysis-daily",
    name: "Reanálise diária",
    description: "",
    kind: "MODELED",
    resolution: "day",
    spatial: "12 pontos",
    source_code: "open-meteo-archive",
    source_name: "Open-Meteo",
    attribution: "Open-Meteo.com (CC BY 4.0)",
    license: "CC BY 4.0",
    freshness: "FRESH",
    variables: [
      { code: "precipitation_sum", label: "Chuva diária", unit: "mm", aggregations: ["sum", "mean", "min", "max"] },
      { code: "air_temperature_max", label: "Temperatura máxima", unit: "°C", aggregations: ["mean", "min", "max"] },
    ],
    grains: ["day", "week", "month", "year"],
    visualizations: ["line", "bar", "area", "histogram", "box", "calendar", "ranking", "table"],
    numeric: true,
    caveats: [],
    records: 13106,
    period_start: "1991-01-01",
    period_end: "2026-11-18",
    locations: [
      { key: "-23.5700,-46.6200", label: "Centro", latitude: -23.57, longitude: -46.62, detail: null },
      { key: "-23.6900,-46.6200", label: "Sul (~16 km do centro)", latitude: -23.69, longitude: -46.62, detail: null },
    ],
    ...overrides,
  };
}

const iag = dataset({
  id: "iag-rain-monthly",
  kind: "OBSERVED",
  resolution: "month",
  variables: [{ code: "precipitation_month", label: "Chuva mensal", unit: "mm", aggregations: ["sum", "mean", "min", "max"] }],
  grains: ["month", "year"],
  visualizations: ["line", "bar", "histogram", "box", "table"],
  period_start: "1933-01",
  period_end: "2025-12",
  locations: [{ key: "IAG-AGUA-FUNDA", label: "IAG/USP — Água Funda", latitude: -23.65, longitude: -46.62, detail: null }],
});

describe("Studio (FR-094, AC-086)", () => {
  it("calendário só com dados diários; ranking só com mais de um local", () => {
    const reanalysis = dataset({});
    expect(compatibleVisualizations(reanalysis, "day")).toContain("calendar");
    expect(compatibleVisualizations(reanalysis, "month")).not.toContain("calendar");
    expect(compatibleVisualizations(iag, "month")).not.toContain("calendar");
    expect(compatibleVisualizations(iag, "month")).not.toContain("ranking");
  });

  it("normal só para conjuntos com climatologia, por mês ou ano", () => {
    expect(compatibleComparisons(dataset({}), "month")[0]).toBe("normal");
    expect(compatibleComparisons(dataset({}), "day")).not.toContain("normal");
    expect(compatibleComparisons(dataset({ id: "flood-occurrences" }), "month")).not.toContain("normal");
  });

  it("estado ↔ URL, recusando valores incompatíveis", () => {
    const datasets = [dataset({}), iag];
    const state = parseStudio(
      new URLSearchParams(
        "conjunto=reanalysis-daily&variavel=air_temperature_max&agregacao=sum&agrupar=month&visual=calendar&local=-23.6900,-46.6200&inicio=2025-01-01&fim=2025-12-31&comparar=normal",
      ),
      datasets,
      "2026-11-18",
    );
    expect(state).toMatchObject({
      dataset: "reanalysis-daily",
      variable: "air_temperature_max",
      agg: "mean", // soma de temperatura recusada
      grain: "month",
      viz: "line", // calendário não serve para mês
      location: "-23.6900,-46.6200",
      compare: "normal",
    });
    const round = parseStudio(new URLSearchParams(serializeStudio(state!)), datasets, "2026-11-18");
    expect(round).toEqual(state);
    const fallback = parseStudio(new URLSearchParams("conjunto=xyz"), datasets, "2026-11-18");
    expect(fallback?.dataset).toBe("reanalysis-daily");
  });

  it("padrões por conjunto", () => {
    const s = defaultState(iag, "2026-11-18");
    expect(s).toMatchObject({ dataset: "iag-rain-monthly", grain: "month", agg: "sum", end: "2025-12-31", start: "2023-01-01" });
  });

  it("consulta e CSV usam os mesmos parâmetros (AC-087)", () => {
    const params = {
      dataset: "reanalysis-daily",
      variable: "precipitation_sum",
      start: "2026-11-01",
      end: "2026-11-18",
      grain: "day",
      agg: "sum",
      location: "-23.5700,-46.6200",
      compare: null,
    };
    expect(seriesQuery(params)).toBe(
      "dataset=reanalysis-daily&variable=precipitation_sum&start=2026-11-01&end=2026-11-18&grain=day&agg=sum&location=-23.5700%2C-46.6200",
    );
    expect(seriesCsvUrl(params)).toBe(`/api/v1/analytics/series.csv?${seriesQuery(params)}`);
  });

  it("histograma de faixas iguais", () => {
    expect(equalBins([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5).map((b) => b.n)).toEqual([2, 2, 2, 2, 3]);
    expect(equalBins([]).length).toBe(0);
    expect(equalBins([3, 3, 3])).toEqual([{ low: 3, high: 3, n: 3 }]);
  });
});

describe("formatação", () => {
  it("períodos e unidades", () => {
    expect(periodLabel("2026-11-01", "month")).toBe("nov/2026");
    expect(periodLabel("2026-01-01", "year")).toBe("2026");
    expect(periodLabel("2026-11-18", "day")).toBe("18/11/2026");
    expect(mm(1559.2)).toBe("1.559,2 mm");
    expect(mm(null)).toBe("—");
    expect(pct(0.875)).toBe("88%");
  });
});

describe("moldura dos gráficos (NFR-083)", () => {
  it("tem resumo, tipo, fonte e tabela equivalente", async () => {
    const { container } = render(
      <ChartFrame
        id="teste"
        title="Chuva mensal"
        summary="Barras: chuva de cada mês."
        kind="OBSERVED"
        source="IAG/USP"
        notes={["Uma estação."]}
        rows={[{ mes: "jan", chuva: 272.6 }]}
        columns={[
          { key: "mes", label: "Mês" },
          { key: "chuva", label: "Chuva", format: mm },
        ]}
      >
        <div />
      </ChartFrame>,
    );
    expect(screen.getByRole("img", { name: /Chuva mensal\. Barras: chuva de cada mês\./ })).toBeInTheDocument();
    expect(screen.getByText("Medido")).toBeInTheDocument();
    const table = screen.getByRole("table", { hidden: true });
    expect(within(table).getByText("272,6 mm")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });
});

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("intervalLabel", () => {
  it("mostra intervalos longos em dias", async () => {
    const { intervalLabel } = await import("@/components/analytics/SourcesTab");
    expect(intervalLabel(1)).toBe("1 h");
    expect(intervalLabel(24)).toBe("24 h");
    expect(intervalLabel(9600)).toBe("400 dias");
  });
});
