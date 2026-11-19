import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { ReadinessView } from "@/components/system/ReadinessView";
import type { ReadinessReport } from "@/features/system/types";

const degraded: ReadinessReport = {
  status: "degraded",
  checked_at: "2026-11-19T15:00:00Z",
  components: {
    db: { status: "ok", latency_ms: 2.4, detail: null, info: {} },
    postgis: { status: "ok", latency_ms: 3.1, detail: null, info: { versão: "3.4.3" } },
    redis: { status: "unavailable", latency_ms: null, detail: "sem resposta em 2 s", info: {} },
    worker: { status: "ok", latency_ms: 812.5, detail: null, info: { "workers ativos": "1" } },
  },
};

const ok: ReadinessReport = {
  ...degraded,
  status: "ok",
  components: {
    ...degraded.components,
    redis: { status: "ok", latency_ms: 0.9, detail: null, info: {} },
  },
};

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("ReadinessView", () => {
  it("estado de carregamento é anunciado para leitores de tela", () => {
    render(<ReadinessView state="loading" onRetry={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Verificando o estado do sistema");
  });

  it("sucesso mostra cada componente com estado em texto (não só cor)", async () => {
    const { container } = render(<ReadinessView state="success" report={ok} onRetry={() => {}} />);
    expect(screen.getByText("Todos os componentes operacionais")).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(4);
    for (const row of rows) expect(within(row).getByText("Operacional")).toBeInTheDocument();
    expect(screen.getByText("versão: 3.4.3")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tentar novamente" })).not.toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("degradado destaca o componente com falha e oferece nova tentativa", async () => {
    const onRetry = vi.fn();
    const { container } = render(
      <ReadinessView state="degraded" report={degraded} onRetry={onRetry} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Operação degradada");
    const redisRow = screen.getByRole("row", { name: /Redis/ });
    expect(within(redisRow).getByText("Indisponível")).toBeInTheDocument();
    expect(within(redisRow).getByText("sem resposta em 2 s")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("erro (AC-005) mostra mensagem compreensível, código de suporte e nova tentativa", async () => {
    const onRetry = vi.fn();
    const { container } = render(
      <ReadinessView
        state="error"
        errorMessage="Não foi possível conectar à API."
        correlationId="abc123"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("API inacessível");
    expect(screen.getByText(/Não foi possível conectar à API/)).toBeInTheDocument();
    expect(screen.getByText("abc123")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("sem conexão explica a situação", () => {
    render(<ReadinessView state="offline" onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Sem conexão");
  });

  it("botão de nova tentativa fica desabilitado durante a verificação", () => {
    render(<ReadinessView state="error" isRefreshing onRetry={() => {}} />);
    expect(screen.getByRole("button", { name: "Verificando…" })).toBeDisabled();
  });

  it("mostra o horário da verificação em Brasília, com UTC no título", () => {
    render(<ReadinessView state="success" report={ok} onRetry={() => {}} />);
    const time = screen.getByText("19/11/2026, 12:00:00");
    expect(time).toHaveAttribute("dateTime", "2026-11-19T15:00:00Z");
  });
});
