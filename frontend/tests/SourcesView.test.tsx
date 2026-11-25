import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { SourcesView } from "@/components/system/SourcesView";
import { fetchSourcesStatus } from "@/features/sources/api";
import type { SourceStatus } from "@/features/sources/types";

const base: SourceStatus = {
  code: "open-meteo-forecast",
  name: "Open-Meteo — previsão do tempo",
  owner: "Open-Meteo",
  url: "https://api.open-meteo.com/v1/forecast",
  license: "CC BY 4.0 (uso não comercial da API gratuita)",
  attribution: "Dados de previsão: Open-Meteo.com (CC BY 4.0)",
  access_method: "API REST (JSON), sem token",
  expected_interval_s: 3600,
  freshness: "FRESH",
  reason: "ok",
  last_success_at: "2026-11-19T17:00:00Z",
  last_attempt_at: "2026-11-19T17:00:00Z",
  last_run_status: "SUCCESS",
  last_error: null,
};

const items: SourceStatus[] = [
  base,
  {
    ...base,
    code: "inmet-observations",
    name: "INMET — observações horárias",
    freshness: "UNAVAILABLE",
    reason: "missing_credentials",
    last_success_at: null,
    attribution: "Fonte: INMET",
  },
];

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("SourcesView (FR-032)", () => {
  it("mostra frescor, motivo, última coleta e atribuição de cada fonte", async () => {
    const { container } = render(<SourcesView state="success" items={items} onRetry={() => {}} />);
    const cards = screen.getAllByRole("listitem");
    expect(cards).toHaveLength(2);
    const openMeteo = within(cards[0]!);
    expect(openMeteo.getByText("Atualizado")).toBeInTheDocument();
    expect(openMeteo.getByText("19/11/2026, 14:00:00")).toBeInTheDocument();
    expect(openMeteo.getByText("a cada 1 h")).toBeInTheDocument();
    expect(openMeteo.getByText(/Open-Meteo.com \(CC BY 4.0\)/)).toBeInTheDocument();
    const inmet = within(cards[1]!);
    expect(inmet.getByText("Indisponível")).toBeInTheDocument();
    expect(inmet.getByText("Credencial (token) não configurada.")).toBeInTheDocument();
    expect(inmet.getByText("nunca")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("carregando é anunciado para leitores de tela", () => {
    render(<SourcesView state="loading" onRetry={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando o estado das fontes");
  });

  it("erro oferece nova tentativa", () => {
    const onRetry = vi.fn();
    render(<SourcesView state="error" errorMessage="Falha de rede." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível obter o estado das fontes");
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("lista vazia é explicada", () => {
    render(<SourcesView state="success" items={[]} onRetry={() => {}} />);
    expect(screen.getByText("Nenhuma fonte cadastrada.")).toBeInTheDocument();
  });
});

describe("fetchSourcesStatus", () => {
  it("consulta a rota relativa da API", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ checked_at: "2026-11-19T17:00:00Z", items }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await fetchSourcesStatus(undefined, fetchImpl);
    expect(result.items).toHaveLength(2);
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/sources/status", expect.anything());
  });
});
