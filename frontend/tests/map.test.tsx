import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { MapFeatureList } from "@/components/map/MapFeatureList";
import { MapLegend } from "@/components/map/MapLegend";
import { MapControls } from "@/components/map/MapControls";
import { COLUMN_MAX_M, circlePolygon, columnHeight, rainClass } from "@/features/map/geometry";
import { DEFAULT_STATE, parseMapState, serializeMapState, toggleLayer } from "@/features/map/state";
import type { FeatureCollection, ForecastPointProps, StationProps } from "@/features/map/types";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("estado do mapa na URL (FR-059, AC-052)", () => {
  it("padrão é 3D com todas as camadas", () => {
    expect(parseMapState(new URLSearchParams(""))).toEqual(DEFAULT_STATE);
  });

  it("lê e escreve modo e camadas, ignorando valores inválidos", () => {
    const state = parseMapState(new URLSearchParams("modo=2d&camadas=chuva,xyz,estacoes"));
    expect(state).toEqual({ mode: "2d", layers: ["estacoes", "chuva"] });
    expect(serializeMapState(state)).toBe("modo=2d&camadas=estacoes%2Cchuva");
    expect(parseMapState(new URLSearchParams("modo=4d&camadas=")).mode).toBe("3d");
    expect(parseMapState(new URLSearchParams("camadas=")).layers).toEqual([]);
  });

  it("alterna camadas mantendo a ordem", () => {
    const off = toggleLayer(DEFAULT_STATE, "chuva");
    expect(off.layers).toEqual(["estacoes", "locais", "regiao"]);
    expect(toggleLayer(off, "chuva").layers).toEqual(["estacoes", "chuva", "locais", "regiao"]);
  });
});

describe("escalas e geometria (BR-050, BR-051)", () => {
  it("classifica a chuva em faixas", () => {
    expect(rainClass(0).id).toBe("sem");
    expect(rainClass(1.7).id).toBe("fraca");
    expect(rainClass(5).id).toBe("moderada");
    expect(rainClass(26.3).id).toBe("forte");
    expect(rainClass(80).id).toBe("muito-forte");
  });

  it("altura da coluna é linear e tem teto", () => {
    expect(columnHeight(0)).toBe(150);
    expect(columnHeight(10)).toBe(750);
    expect(columnHeight(1000)).toBe(COLUMN_MAX_M);
    expect(columnHeight(-5)).toBe(150);
  });

  it("círculo é um anel fechado com raio aproximado", () => {
    const ring = circlePolygon(-46.63, -23.55, 1000, 16);
    expect(ring).toHaveLength(17);
    expect(ring[0]).toEqual(ring[16]);
    const [lon, lat] = ring[4]!; // 90°: deslocamento só em latitude
    expect(lon).toBeCloseTo(-46.63, 6);
    expect((lat - -23.55) * 111_195).toBeCloseTo(1000, -1);
  });
});

const stations: FeatureCollection<StationProps> = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: 2,
      geometry: { type: "Point", coordinates: [-46.620067, -23.496289] },
      properties: { id: 2, code: "A701", name: "SAO PAULO - MIRANTE", status: "OPERATIONAL", source: "inmet-stations", altitude_m: 785.64 },
    },
  ],
};

const forecast: FeatureCollection<ForecastPointProps> = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: 1,
      geometry: { type: "Point", coordinates: [-46.610504, -23.514938] },
      properties: {
        point_key: "-23.5149,-46.6105",
        kind: "FORECAST",
        issued_at: "2026-11-19T18:58:56Z",
        valid_from: "2026-11-19T19:00:00Z",
        air_temperature_now: 29.5,
        precipitation_24h: 2.1,
        precipitation_24h_complete: false,
        precipitation_24h_hours: 20,
      },
    },
  ],
};

describe("lista, legenda e controles (FR-056, FR-057, AC-050)", () => {
  it("lista estações e pontos de previsão com links para o clima", async () => {
    const { container } = render(<MapFeatureList stations={stations} forecast={forecast} />);
    const stationRow = screen.getByRole("row", { name: /MIRANTE/ });
    expect(within(stationRow).getByText("Operante")).toBeInTheDocument();
    expect(within(stationRow).getByRole("link", { name: "Ver clima" })).toHaveAttribute(
      "href",
      expect.stringContaining("/weather?lat=-23.4963&lon=-46.6201"),
    );
    expect(screen.getByText("2,1 (parcial: 20 h)")).toBeInTheDocument();
    expect(screen.getByText("Fraca (até 5 mm)")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("legenda descreve cores com texto e explica a altura em 3D", async () => {
    const { container } = render(<MapLegend mode="3d" />);
    expect(screen.getByText("Em pane")).toBeInTheDocument();
    expect(screen.getByText("Muito forte (acima de 50 mm)")).toBeInTheDocument();
    expect(screen.getByText(/altura da coluna proporcional/)).toBeInTheDocument();
    expect(screen.getByText("Faixas visuais, não são alertas oficiais.")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("controles indicam o modo ativo e ficam desabilitados sem WebGL", () => {
    const { rerender } = render(
      <MapControls mode="3d" layers={["chuva"]} webgl onModeChange={() => {}} onToggleLayer={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "3D com relevo" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("checkbox", { name: "Chuva prevista (24 h)" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Estações do INMET" })).not.toBeChecked();
    rerender(<MapControls mode="3d" layers={[]} webgl={false} onModeChange={() => {}} onToggleLayer={() => {}} />);
    expect(screen.getByRole("button", { name: "2D plano" })).toBeDisabled();
  });
});
