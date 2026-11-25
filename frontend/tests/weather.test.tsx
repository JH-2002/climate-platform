import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { DailyTable } from "@/components/weather/DailyTable";
import { HourlyChart } from "@/components/weather/HourlyChart";
import { NearbyStations } from "@/components/weather/NearbyStations";
import { NowCard } from "@/components/weather/NowCard";
import { RainOutlook } from "@/components/weather/RainOutlook";
import { SourceNote } from "@/components/weather/SourceNote";
import { fetchForecast } from "@/features/weather/api";
import type { ForecastResponse, HourlyValues } from "@/features/weather/types";

const now: HourlyValues = {
  valid_at: "2026-11-19T15:00:00Z",
  air_temperature: 30.2,
  precipitation: 0.1,
  relative_humidity: 48,
  wind_speed: 2.694,
};

const forecast: ForecastResponse = {
  kind: "FORECAST",
  point: { latitude: -23.5149, longitude: -46.6105, distance_km: 6.3 },
  source: {
    code: "open-meteo-forecast",
    name: "Open-Meteo — previsão do tempo",
    attribution: "Dados de previsão: Open-Meteo.com (CC BY 4.0)",
    freshness: "FRESH",
    reason: "ok",
    last_success_at: "2026-11-19T15:05:00Z",
  },
  issued_at: "2026-11-19T15:05:00Z",
  now,
  hourly: [now, { ...now, valid_at: "2026-11-19T16:00:00Z", air_temperature: 30.8, precipitation: 0 }],
  daily: [
    {
      date: "2026-11-20",
      air_temperature_max: 31.6,
      air_temperature_min: 20.8,
      precipitation_sum: 1.8,
      precipitation_probability_max: 78,
    },
  ],
  precipitation_outlook: [
    { hours: 1, total_mm: 0.1, complete: true, hours_available: 1 },
    { hours: 3, total_mm: 0.1, complete: false, hours_available: 2 },
  ],
  units: { air_temperature: "°C" },
};

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("NowCard (AC-044)", () => {
  it("rotula a estimativa como modelo e mostra unidades", async () => {
    const { container } = render(<NowCard now={now} />);
    expect(screen.getByText("Estimativa de modelo — não é medição")).toBeInTheDocument();
    expect(screen.getByText("30,2")).toBeInTheDocument();
    expect(screen.getByText("9,7")).toBeInTheDocument(); // 2,694 m/s -> 9,7 km/h
    expect(screen.getByText("(12:00)")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("explica quando a hora atual não está na previsão", () => {
    render(<NowCard now={null} />);
    expect(screen.getByText(/não cobre a hora atual/)).toBeInTheDocument();
  });
});

describe("RainOutlook (FR-043, BR-041, BR-043)", () => {
  it("mostra acumulados previstos, avisa os parciais e explica a chuva medida", () => {
    render(<RainOutlook outlook={forecast.precipitation_outlook} observationsAvailable={false} />);
    expect(screen.getByText("Próxima 1 h")).toBeInTheDocument();
    expect(screen.getByText("Parcial: 2 de 3 h disponíveis")).toBeInTheDocument();
    expect(screen.getByText(/aguardam o token de acesso/)).toBeInTheDocument();
  });
});

describe("DailyTable e HourlyChart", () => {
  it("tabela diária com dia local e unidades no cabeçalho", async () => {
    const { container } = render(<DailyTable days={forecast.daily} />);
    const row = screen.getAllByRole("row")[1]!;
    expect(within(row).getByText(/20\/11/)).toBeInTheDocument();
    expect(within(row).getByText("31,6")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Chuva (mm)" })).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("gráfico tem alternativa em tabela (NFR-041)", () => {
    render(<HourlyChart hours={forecast.hourly} />);
    expect(screen.getByRole("img", { name: /Gráfico de temperatura/ })).toBeInTheDocument();
    expect(screen.getByText("Ver dados em tabela")).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "13:00" })).toBeInTheDocument();
  });

  it("estados vazios são explicados", () => {
    render(<HourlyChart hours={[]} />);
    expect(screen.getByText(/Sem previsão horária/)).toBeInTheDocument();
  });
});

describe("SourceNote e NearbyStations (FR-046, FR-047)", () => {
  it("informa origem, distância e atribuição", () => {
    render(<SourceNote forecast={forecast} />);
    expect(screen.getByText(/Previsão de modelo \(não é medição\)/)).toBeInTheDocument();
    expect(screen.getByText(/6,3 km/)).toBeInTheDocument();
    expect(screen.getByText(/CC BY 4.0/)).toBeInTheDocument();
  });

  it("avisa quando a previsão está atrasada", () => {
    render(<SourceNote forecast={{ ...forecast, source: { ...forecast.source, freshness: "STALE", reason: "stale" } }} />);
    expect(screen.getByText("Desatualizado")).toBeInTheDocument();
  });

  it("lista estações com distância, situação e disponibilidade das medições", () => {
    render(
      <NearbyStations
        state="success"
        observationsAvailable={false}
        stations={[
          { id: 2, code: "A701", name: "SAO PAULO - MIRANTE", status: "OPERATIONAL", latitude: -23.49, longitude: -46.62, distance_km: 8.09 },
          { id: 3, code: "A755", name: "BARUERI", status: "FAULT", latitude: -23.52, longitude: -46.87, distance_km: 22.4 },
        ]}
      />,
    );
    expect(screen.getByText("Operante")).toBeInTheDocument();
    expect(screen.getByText("Em pane")).toBeInTheDocument();
    expect(screen.getAllByText(/aguardando token do INMET/)).toHaveLength(2);
  });
});

describe("fetchForecast", () => {
  it("chama a rota relativa com coordenadas arredondadas", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(forecast), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    await fetchForecast(-23.561412, -46.655912, undefined, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/weather/forecast?lat=-23.5614&lon=-46.6559",
      expect.anything(),
    );
  });
});
